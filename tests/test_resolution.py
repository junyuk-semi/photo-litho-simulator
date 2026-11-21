"""Unit tests for Stage 2: Rayleigh resolution, High-NA/Immersion DOF, OAI, and plots."""

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

from src.physics.resolution import (
    analyze_node,
    compare_all_nodes,
    depth_of_focus,
    effective_k1,
    exposure_dose,
    rayleigh_resolution,
    required_exposure_time,
    sweep_na_curve,
    sweep_wavelength_na_grid,
)
from src.visualization.resolution_plots import (
    plot_node_comparison,
    plot_resolution_dof_tradeoff,
    plot_resolution_vs_na,
)


class TestStage2Resolution(unittest.TestCase):
    def test_rayleigh_scaling_laws(self) -> None:
        # Shorter wavelength -> smaller CD
        cd_krf = rayleigh_resolution(248.0, 0.85, k1=0.35)
        cd_arf = rayleigh_resolution(193.0, 0.85, k1=0.35)
        cd_euv = rayleigh_resolution(13.5, 0.33, k1=0.35)
        self.assertLess(cd_arf, cd_krf)
        self.assertLess(cd_euv, cd_arf)

        # Higher NA -> smaller CD
        cd_low_na = rayleigh_resolution(193.0, 0.70, k1=0.35)
        cd_high_na = rayleigh_resolution(193.0, 1.35, k1=0.35)
        self.assertLess(cd_high_na, cd_low_na)

        # Exact formula check: 0.35 * 193 / 1.35
        self.assertAlmostEqual(cd_high_na, 0.35 * 193.0 / 1.35, places=10)

    def test_high_na_dof_converges_to_paraxial_at_small_na(self) -> None:
        dof_hi = depth_of_focus(193.0, 0.10, k2=0.50, n_fluid=1.0, high_na=True)
        dof_par = depth_of_focus(193.0, 0.10, k2=0.50, n_fluid=1.0, high_na=False)
        rel_err = abs(dof_hi - dof_par) / dof_par
        self.assertLess(rel_err, 0.005)

    def test_immersion_dof_gain_and_na_monotonicity(self) -> None:
        # Higher NA -> smaller DOF
        dof_low = depth_of_focus(193.0, 0.70, k2=0.50, n_fluid=1.44, high_na=True)
        dof_high = depth_of_focus(193.0, 1.35, k2=0.50, n_fluid=1.44, high_na=True)
        self.assertLess(dof_high, dof_low)

        # Immersion (n=1.44) gives strictly larger DOF than Dry (n=1.0) at equal NA=0.85
        dof_dry = depth_of_focus(193.0, 0.85, k2=0.50, n_fluid=1.00, high_na=True)
        dof_imm = depth_of_focus(193.0, 0.85, k2=0.50, n_fluid=1.44, high_na=True)
        self.assertGreater(dof_imm, dof_dry * 1.40)

    def test_oai_effects_and_physical_k1_floor(self) -> None:
        k1_conv = effective_k1(0.35, "Conventional")
        k1_ann = effective_k1(0.35, "Annular")
        k1_dip = effective_k1(0.35, "Dipole")
        self.assertLess(k1_dip, k1_ann)
        self.assertLess(k1_ann, k1_conv)

        # Clamped at physical single-patterning limit 0.25
        self.assertEqual(effective_k1(0.26, "Dipole", clamp_physical_limit=True), 0.25)

        # Dipole improves Dense DOF but reduces Isolated DOF
        dof_dense_conv = depth_of_focus(193.0, 1.35, n_fluid=1.44, illumination="Conventional", pattern="Dense_1to1")
        dof_dense_dip = depth_of_focus(193.0, 1.35, n_fluid=1.44, illumination="Dipole", pattern="Dense_1to1")
        dof_iso_conv = depth_of_focus(193.0, 1.35, n_fluid=1.44, illumination="Conventional", pattern="Isolated_Line")
        dof_iso_dip = depth_of_focus(193.0, 1.35, n_fluid=1.44, illumination="Dipole", pattern="Isolated_Line")
        self.assertGreater(dof_dense_dip, dof_dense_conv)
        self.assertLess(dof_iso_dip, dof_iso_conv)

    def test_exposure_dose_week9_slide12_example(self) -> None:
        # Week 9 Slide 12: 0.5 mW/cm^2 * 10 sec = 5.0 mW*sec/cm^2 (mJ/cm^2)
        dose = exposure_dose(0.5, 10.0)
        self.assertAlmostEqual(dose, 5.0, places=10)
        self.assertAlmostEqual(required_exposure_time(5.0, 0.5), 10.0, places=10)

    def test_node_analysis_and_sweeps(self) -> None:
        results = compare_all_nodes(illumination="Annular", pattern="Dense_1to1")
        self.assertEqual(len(results), 4)
        self.assertTrue(results[-1].comparison_only)
        self.assertFalse(results[2].comparison_only)

        arfi = analyze_node("ArFi_193", illumination="Annular", target_cd_nm=45.0)
        self.assertTrue(arfi.is_resolvable)

        sweep = sweep_na_curve(193.0, 0.65, 1.35, n_points=50, n_fluid=1.44)
        self.assertEqual(sweep["na"].shape, (50,))
        self.assertTrue(np.all(np.diff(sweep["min_cd_nm"]) < 0))
        self.assertTrue(np.all(np.diff(sweep["dof_high_na_nm"]) < 0))

        wl_m, na_m, cd_m = sweep_wavelength_na_grid([193.0, 248.0], [0.7, 0.85, 1.35])
        self.assertEqual(cd_m.shape, (2, 3))

    def test_invalid_inputs_raise_errors(self) -> None:
        with self.assertRaises(ValueError):
            depth_of_focus(193.0, 1.05, n_fluid=1.0, high_na=True)
        with self.assertRaises(ValueError):
            rayleigh_resolution(-193.0, 0.85)
        with self.assertRaises(ValueError):
            required_exposure_time(10.0, 0.0)

    def test_stage2_plot_builders_smoke(self) -> None:
        for fig in (
            plot_resolution_vs_na(),
            plot_resolution_dof_tradeoff(),
            plot_node_comparison(),
        ):
            self.assertIsNotNone(fig)
            plt.close(fig)


if __name__ == "__main__":
    unittest.main()
