"""Unit tests for Stage 8: Real-World Fab Sequential Flow, Run-to-Run Cycle & CAPA Report."""

from __future__ import annotations

import unittest

import numpy as np

from src.fab_cycle import (
    FabRecipe,
    build_cumulative_summary_markdown,
    preset_recipes,
    run_fab_cycle,
)


class TestFabCycle(unittest.TestCase):
    def test_stepwise_run_to_run_yield_improvement(self) -> None:
        r1 = list(preset_recipes("ArFi_193").values())[0]
        c1 = run_fab_cycle(r1, cycle_id=1)
        c2 = run_fab_cycle(c1.recommended_stepwise_recipe, cycle_id=2)
        c3 = run_fab_cycle(c2.recommended_stepwise_recipe, cycle_id=3)

        self.assertLess(c1.aci_yield_pct, 65.0)
        self.assertGreater(c1.optics.substrate_reflectance, 0.15)
        self.assertGreater(len(c1.action_items), 0)

        self.assertGreater(c2.aci_yield_pct, c1.aci_yield_pct)
        self.assertLess(c2.optics.substrate_reflectance, 0.02)

        self.assertGreaterEqual(c3.aci_yield_pct, c2.aci_yield_pct)
        self.assertGreaterEqual(c3.aci_yield_pct, 95.0)
        self.assertLess(c3.aci_cdu_3sigma_nm, c1.aci_cdu_3sigma_nm)

    def test_etch_bias_and_adi_aci_consistency(self) -> None:
        rec = FabRecipe(etch_bias_nm=-3.0, target_aci_cd_nm=45.0)
        c = run_fab_cycle(rec, cycle_id=1)
        self.assertAlmostEqual(c.target_adi_cd_nm, 48.0, places=5)
        np.testing.assert_allclose(c.aci_cd_sites_nm, np.maximum(0.0, c.wafer_cdu.cd_nm - 3.0))

    def test_report_contains_analysis_and_capa(self) -> None:
        r1 = list(preset_recipes("ArFi_193").values())[0]
        c1 = run_fab_cycle(r1, cycle_id=1)
        self.assertIn("공정 결과 성적표", c1.report_markdown)
        self.assertIn("데이터 분석", c1.report_markdown)
        self.assertIn("향후 필요한 조치사항", c1.report_markdown)

        summary = build_cumulative_summary_markdown([c1, run_fab_cycle(c1.recommended_full_recipe, cycle_id=2)])
        self.assertIn("누적 성적 비교표", summary)


if __name__ == "__main__":
    unittest.main()
