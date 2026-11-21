"""Unit tests for Stage 3 (TMM Multilayer Optics) and Stage 4 (Optics-Coupled FEM & PW)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.physics.exposure_fem import bossung_cd, evaluate_defects, simulate_fem
from src.physics.optics_tmm import (
    LayerSpec,
    build_litho_stack,
    compute_swing_curve,
    optimize_barc_thickness,
    simulate_multilayer_optics,
)
from src.visualization.optics_fem_plots import (
    plot_fem_heatmap_and_bossung,
    plot_standing_wave_comparison,
    plot_swing_curve_and_barc_opt,
)


class TestStage3OpticsTMM(unittest.TestCase):
    def test_zero_reflection_for_matched_lossless_stack(self) -> None:
        layers = [
            LayerSpec("Ambient", 1.5, 0.0, np.inf),
            LayerSpec("PR", 1.5, 0.0, 150.0),
            LayerSpec("BARC", 1.5, 0.0, 50.0),
            LayerSpec("Sub", 1.5, 0.0, np.inf),
        ]
        res = simulate_multilayer_optics(layers, wavelength_nm=193.0)
        self.assertAlmostEqual(res.reflectance, 0.0, places=12)
        self.assertAlmostEqual(res.transmittance, 1.0, places=12)
        self.assertAlmostEqual(res.absorptance, 0.0, places=12)
        self.assertAlmostEqual(res.swr_local, 1.0, places=10)
        self.assertAlmostEqual(res.effective_dose_factor, 1.0, places=10)

    def test_energy_conservation_across_all_underlayers(self) -> None:
        for ul in ("Bare_Si", "SiO2", "PolySi", "Al_Metal"):
            for barc in (0.0, 40.0):
                stack = build_litho_stack(
                    wavelength_nm=193.0,
                    ambient_material="Water_Immersion",
                    pr_thickness_nm=120.0,
                    barc_thickness_nm=barc,
                    underlayer_material=ul,
                    underlayer_thickness_nm=100.0,
                )
                res = simulate_multilayer_optics(stack, wavelength_nm=193.0)
                self.assertGreaterEqual(res.reflectance, 0.0)
                self.assertGreaterEqual(res.transmittance, 0.0)
                self.assertGreaterEqual(res.absorptance, 0.0)
                self.assertAlmostEqual(
                    res.reflectance + res.transmittance + res.absorptance, 1.0, places=10
                )

    def test_standing_wave_period_matches_lambda_over_2n(self) -> None:
        # Lossless PR on high-reflectance Al metal produces clean standing waves with period lambda/(2n)
        wl = 193.0
        n_pr = 1.70
        expected_period = wl / (2.0 * n_pr)
        layers = [
            LayerSpec("Air", 1.0, 0.0, np.inf),
            LayerSpec("PR", n_pr, 0.0, 300.0),
            LayerSpec("Al_Metal", 0.11, 2.20, np.inf),
        ]
        res = simulate_multilayer_optics(layers, wavelength_nm=wl, n_z_points=1201)
        # Locate local maxima indices
        y = res.intensity_z
        peaks = np.where((y[1:-1] > y[:-2]) & (y[1:-1] > y[2:]))[0] + 1
        self.assertGreaterEqual(len(peaks), 3)
        spacings = np.diff(res.z_nm[peaks])
        self.assertAlmostEqual(float(np.mean(spacings)), expected_period, delta=0.5)

    def test_barc_suppresses_reflectance_and_swing_amplitude(self) -> None:
        for ul in ("Bare_Si", "Al_Metal"):
            opt = optimize_barc_thickness(
                wavelength_nm=193.0,
                ambient_material="Water_Immersion",
                pr_thickness_nm=120.0,
                underlayer_material=ul,
            )
            self.assertLess(opt["min_substrate_reflectance"], opt["no_barc_substrate_reflectance"] * 0.25)

            swing_off = compute_swing_curve(
                wavelength_nm=193.0, barc_thickness_nm=0.0, underlayer_material=ul, n_points=50
            )
            swing_on = compute_swing_curve(
                wavelength_nm=193.0,
                barc_thickness_nm=float(opt["optimal_barc_nm"]),
                underlayer_material=ul,
                n_points=50,
            )
            self.assertLess(
                float(swing_on["reflectance_swing_amplitude"]),
                float(swing_off["reflectance_swing_amplitude"]) * 0.40,
            )


class TestStage4OpticsCoupledFEM(unittest.TestCase):
    def test_positive_pr_dose_monotonicity_and_defocus_symmetry(self) -> None:
        doses = np.linspace(18.0, 40.0, 40)
        cds = bossung_cd(doses, 0.0, target_cd_nm=45.0, nominal_dose_mj_cm2=28.0, dof_scale_nm=65.0)
        # Dose increase -> Line CD strictly decreases
        self.assertTrue(np.all(np.diff(cds) < 0))

        # Symmetry around Best Focus (dz = 0)
        cd_pos = bossung_cd(28.0, +60.0, target_cd_nm=45.0, nominal_dose_mj_cm2=28.0, dof_scale_nm=65.0)
        cd_neg = bossung_cd(28.0, -60.0, target_cd_nm=45.0, nominal_dose_mj_cm2=28.0, dof_scale_nm=65.0)
        self.assertAlmostEqual(cd_pos, cd_neg, places=10)

    def test_dense_vs_isolated_bossung_curvature_differs(self) -> None:
        fem_dense = simulate_fem("ArFi_193", pattern="Dense_1to1", barc_thickness_nm=40.0)
        fem_iso = simulate_fem("ArFi_193", pattern="Isolated_Line", barc_thickness_nm=40.0)
        self.assertGreater(fem_dense.process_window.pw_area, 0.0)
        self.assertGreater(fem_iso.process_window.pw_area, 0.0)
        # Curvature at nominal dose differs between Dense and Isolated
        mid = len(fem_dense.dose_grid_mj_cm2) // 2
        curv_dense = fem_dense.cd_matrix_nm[mid, 0] - fem_dense.cd_matrix_nm[mid, len(fem_dense.focus_grid_nm) // 2]
        curv_iso = fem_iso.cd_matrix_nm[mid, 0] - fem_iso.cd_matrix_nm[mid, len(fem_iso.focus_grid_nm) // 2]
        self.assertNotAlmostEqual(curv_dense, curv_iso, places=2)

    def test_optics_to_fem_coupling_and_defect_flags(self) -> None:
        # High-reflectance Al without BARC triggers Reflective Notching; optimal BARC suppresses it
        opt_barc = float(
            optimize_barc_thickness(
                wavelength_nm=193.0,
                ambient_material="Water_Immersion",
                pr_thickness_nm=120.0,
                underlayer_material="Al_Metal",
            )["optimal_barc_nm"]
        )
        fem_no_barc = simulate_fem("ArFi_193", underlayer_material="Al_Metal", barc_thickness_nm=0.0)
        fem_barc = simulate_fem("ArFi_193", underlayer_material="Al_Metal", barc_thickness_nm=opt_barc)
        self.assertIn("Reflective Notching", fem_no_barc.defects_at_center.flags)
        self.assertLess(fem_barc.defects_at_center.notching_risk, fem_no_barc.defects_at_center.notching_risk)
        self.assertLess(fem_barc.optics.substrate_reflectance, 0.05)

        # High PR thickness / small CD without HMDS triggers Pattern Collapse
        collapse = evaluate_defects(
            cd_nm=30.0,
            target_cd_nm=30.0,
            pr_thickness_nm=120.0,
            effective_dose_mj_cm2=28.0,
            nominal_dose_mj_cm2=28.0,
            aerial_contrast=0.7,
            substrate_reflectance=0.01,
            swr_local=1.05,
            hmds_score=0.0,
        )
        self.assertIn("Pattern Collapse", collapse.flags)

    def test_stage3_stage4_plots_smoke(self) -> None:
        s0 = build_litho_stack(193.0, "Water_Immersion", 120.0, 0.0, "Al_Metal")
        s1 = build_litho_stack(193.0, "Water_Immersion", 120.0, 42.0, "Al_Metal")
        r0 = simulate_multilayer_optics(s0, 193.0)
        r1 = simulate_multilayer_optics(s1, 193.0)
        sw0 = compute_swing_curve(193.0, barc_thickness_nm=0.0, underlayer_material="Al_Metal", n_points=30)
        sw1 = compute_swing_curve(193.0, barc_thickness_nm=42.0, underlayer_material="Al_Metal", n_points=30)
        bopt = optimize_barc_thickness(193.0, underlayer_material="Al_Metal", n_points=30)
        fem = simulate_fem("ArFi_193", barc_thickness_nm=40.0, n_dose=21, n_focus=25)

        for fig in (
            plot_standing_wave_comparison(r0, r1, "Al_Metal", 42.0),
            plot_swing_curve_and_barc_opt(sw0, sw1, bopt, "Al_Metal"),
            plot_fem_heatmap_and_bossung(fem),
        ):
            self.assertIsNotNone(fig)
            plt.close(fig)


if __name__ == "__main__":
    unittest.main()
