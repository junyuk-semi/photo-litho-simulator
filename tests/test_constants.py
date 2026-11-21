"""Unit tests for Stage 1 physical presets and parameter specifications."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.physics.constants import (
    DEFECT_THRESHOLDS,
    EXPOSURE_NODES,
    ILLUMINATION_PRESETS,
    MATERIAL_OPTICS,
    PARAMETER_SPECS,
    PATTERN_PRESETS,
    get_optical_constants,
    validate_parameter,
)


class TestStage1Constants(unittest.TestCase):
    def test_exposure_nodes_physical_validity(self) -> None:
        self.assertIn("KrF_248", EXPOSURE_NODES)
        self.assertIn("ArF_Dry_193", EXPOSURE_NODES)
        self.assertIn("ArFi_193", EXPOSURE_NODES)
        self.assertIn("EUV_13p5", EXPOSURE_NODES)
        self.assertTrue(EXPOSURE_NODES["EUV_13p5"].comparison_only)

        for node in EXPOSURE_NODES.values():
            self.assertGreater(node.wavelength_nm, 0.0)
            self.assertLessEqual(node.na_min, node.na_default)
            self.assertLessEqual(node.na_default, node.na_max)
            self.assertLess(
                node.na_max,
                node.n_fluid,
                f"{node.key}: NA_max ({node.na_max}) must be < n_fluid ({node.n_fluid})",
            )
            self.assertGreaterEqual(node.k1_default, 0.25)

    def test_optical_constants_validity_and_lookup(self) -> None:
        for opt in MATERIAL_OPTICS.values():
            self.assertGreater(opt.n, 0.0)
            self.assertGreaterEqual(opt.k, 0.0)
            self.assertEqual(opt.n_complex, complex(opt.n, opt.k))

        si_193 = get_optical_constants("Si_Substrate", 193.0)
        self.assertEqual(si_193.wavelength_nm, 193.0)
        self.assertTrue(1.0 <= si_193.n <= 1.2)
        self.assertTrue(2.8 <= si_193.k <= 3.0)

        si_248 = get_optical_constants("Si_Substrate", 248.0)
        self.assertEqual(si_248.wavelength_nm, 248.0)
        self.assertTrue(1.6 <= si_248.n <= 1.8)
        self.assertTrue(3.5 <= si_248.k <= 3.8)

        with self.assertRaises(KeyError):
            get_optical_constants("Unobtainium", 193.0)

    def test_parameter_specs_bounds_and_validation(self) -> None:
        self.assertGreaterEqual(len(PARAMETER_SPECS), 30)
        for key, spec in PARAMETER_SPECS.items():
            self.assertEqual(key, spec.key)
            self.assertLessEqual(spec.min_val, spec.default_val)
            self.assertLessEqual(spec.default_val, spec.max_val)
            self.assertEqual(validate_parameter(key, spec.default_val), float(spec.default_val))

        with self.assertRaises(ValueError):
            validate_parameter("na", 2.0)
        with self.assertRaises(KeyError):
            validate_parameter("nonexistent_param", 1.0)

    def test_illumination_pattern_and_defect_presets(self) -> None:
        # OAI should reduce effective k1 compared to conventional
        conv_k1 = ILLUMINATION_PRESETS["Conventional"].k1_factor
        for key in ("Annular", "Dipole", "Quadrupole"):
            self.assertLess(ILLUMINATION_PRESETS[key].k1_factor, conv_k1)

        self.assertIn("Dense_1to1", PATTERN_PRESETS)
        self.assertIn("Isolated_Line", PATTERN_PRESETS)
        self.assertLess(
            DEFECT_THRESHOLDS["aspect_ratio_collapse_no_hmds"],
            DEFECT_THRESHOLDS["aspect_ratio_collapse_hmds"],
        )


if __name__ == "__main__":
    unittest.main()
