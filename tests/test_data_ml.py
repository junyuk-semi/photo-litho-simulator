"""Unit tests for Stage 5 (Tier 2, Wafer CDU, Synthetic Data, DOE) & Stage 6 (ML, SHAP, Optimizer)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.analysis import (
    compute_correlation_matrix,
    run_2level_factorial_doe,
    run_ols_regression,
)
from src.data.generator import generate_synthetic_fab_dataset
from src.ml.models import run_extrapolation_experiment, train_and_evaluate_cd_models
from src.ml.optimizer import optimize_process_conditions
from src.physics.process_models import (
    mack_dissolution_rate,
    peb_diffusion_length_nm,
    simulate_wafer_cdu_map,
    spin_coating_thickness_nm,
    tier2_process_shift,
)
from src.visualization.data_ml_plots import (
    plot_correlation_heatmap,
    plot_doe_effects,
    plot_extrapolation_proof,
    plot_ml_benchmark_and_shap,
    plot_wafer_cdu_map,
)


class TestStage5ProcessAndData(unittest.TestCase):
    def test_tier2_physical_scaling_laws(self) -> None:
        # Spin coating: higher RPM -> thinner PR; higher viscosity -> thicker PR
        t_low_rpm = spin_coating_thickness_nm(2000.0, 3.0)
        t_high_rpm = spin_coating_thickness_nm(4000.0, 3.0)
        t_high_visc = spin_coating_thickness_nm(4000.0, 12.0)
        self.assertLess(t_high_rpm, t_low_rpm)
        self.assertGreater(t_high_visc, t_high_rpm)

        # Arrhenius PEB diffusion increases with temperature and time
        self.assertGreater(peb_diffusion_length_nm(125.0, 60.0), peb_diffusion_length_nm(110.0, 60.0))

        # Mack dissolution rate: exposed (M -> 0) dissolves much faster than unexposed (M -> 1)
        self.assertGreater(mack_dissolution_rate(0.05), mack_dissolution_rate(0.95) * 100.0)

        # Nominal Tier 2 yields exact 0 bias and 1.0 contrast modifier
        nom = tier2_process_shift()
        self.assertAlmostEqual(nom["process_cd_bias_nm"], 0.0, places=10)
        self.assertAlmostEqual(nom["contrast_modifier"], 1.0, places=10)

    def test_wafer_cdu_map_and_barc_improvement(self) -> None:
        cdu_no_barc = simulate_wafer_cdu_map("ArFi_193", underlayer_material="Al_Metal", barc_thickness_nm=0.0, seed=7)
        cdu_barc = simulate_wafer_cdu_map("ArFi_193", underlayer_material="Al_Metal", barc_thickness_nm=28.0, seed=7)
        self.assertGreater(cdu_barc.x_mm.size, 200)
        self.assertGreater(cdu_no_barc.cdu_3sigma_nm, 0.0)
        self.assertLess(cdu_barc.cdu_3sigma_nm, cdu_no_barc.cdu_3sigma_nm)

    def test_synthetic_generator_correlation_ols_and_doe(self) -> None:
        df = generate_synthetic_fab_dataset(n_samples=180, nodes=("ArFi_193",), seed=11)
        self.assertEqual(len(df), 180)
        self.assertTrue(bool(df["synthetic_data"].all()))

        corr = compute_correlation_matrix(df)
        # Positive PR: Dose correlates negatively with Line CD
        self.assertLess(float(corr.loc["exposure_dose_mj_cm2", "cd_measured_nm"]), -0.3)

        ols = run_ols_regression(df)
        self.assertGreater(ols.r2, 0.70)

        runs_df, effects_df = run_2level_factorial_doe("ArFi_193")
        self.assertEqual(len(runs_df), 16)
        self.assertIn("Dose", set(effects_df["term"]))


class TestStage6MLAndOptimization(unittest.TestCase):
    def test_ml_benchmark_shap_optimizer_and_extrapolation(self) -> None:
        df = generate_synthetic_fab_dataset(n_samples=520, nodes=("ArFi_193",), seed=19)
        bench = train_and_evaluate_cd_models(df, cv_folds=3, random_state=19)
        self.assertEqual(len(bench.metrics_df), 3)
        best_r2 = float(bench.metrics_df.iloc[0]["R2"])
        self.assertGreater(best_r2, 0.85)
        self.assertGreater(len(bench.importance_df), 0)

        opt = optimize_process_conditions(
            node_key="ArFi_193",
            underlayer="Al_Metal",
            surrogate_model=bench.models["XGBoost"],
            n_candidates=300,
            top_k_verify=4,
            seed=19,
        )
        self.assertGreater(opt.best_recipe["PW Area"], 0.0)
        self.assertLess(opt.best_recipe["R_sub (%)"], 5.0)

        # Extrapolation failure proof: Physics RMSE << XGBoost RMSE on unseen 248nm
        extrap = run_extrapolation_experiment(n_train=180, n_test=60, seed=19)
        phys_rmse = float(
            extrap.summary_df.loc[extrap.summary_df["Model"] == "Physics Model (TMM+Bossung)", "Test RMSE (nm)"].iloc[0]
        )
        xgb_rmse = float(
            extrap.summary_df.loc[extrap.summary_df["Model"] == "XGBoost", "Test RMSE (nm)"].iloc[0]
        )
        self.assertLess(phys_rmse, 3.0)
        self.assertGreater(xgb_rmse, 25.0)

        # Smoke test Stage 5 & 6 plots
        cdu = simulate_wafer_cdu_map("ArFi_193", seed=19)
        corr = compute_correlation_matrix(df)
        _, effects_df = run_2level_factorial_doe("ArFi_193")
        for fig in (
            plot_wafer_cdu_map(cdu),
            plot_correlation_heatmap(corr),
            plot_doe_effects(effects_df),
            plot_ml_benchmark_and_shap(bench),
            plot_extrapolation_proof(extrap),
        ):
            self.assertIsNotNone(fig)
            plt.close(fig)


if __name__ == "__main__":
    unittest.main()
