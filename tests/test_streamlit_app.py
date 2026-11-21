"""Stage 7 smoke tests executing all Streamlit pages headlessly via Streamlit AppTest."""

from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_DIR = Path(__file__).resolve().parents[1] / "app"


class TestStage7StreamlitApp(unittest.TestCase):
    def _assert_page_runs_cleanly(self, rel_path: str, timeout: float = 20.0) -> None:
        page_path = APP_DIR / rel_path
        self.assertTrue(page_path.exists(), f"Missing page: {page_path}")
        at = AppTest.from_file(str(page_path), default_timeout=timeout)
        at.run()
        self.assertEqual(
            len(at.exception),
            0,
            f"Streamlit exception in {rel_path}: {[e.message for e in at.exception]}",
        )

    def test_home_page(self) -> None:
        self._assert_page_runs_cleanly("Home.py")

    def test_page1_resolution(self) -> None:
        self._assert_page_runs_cleanly("pages/1_Resolution_and_DOF.py")

    def test_page2_optics_barc(self) -> None:
        self._assert_page_runs_cleanly("pages/2_Optics_and_BARC.py")

    def test_page3_fem_pw(self) -> None:
        self._assert_page_runs_cleanly("pages/3_FEM_and_Process_Window.py")

    def test_page4_wafer_cdu_data(self) -> None:
        self._assert_page_runs_cleanly("pages/4_Wafer_CDU_and_Data_Analysis.py", timeout=30.0)

    def test_page5_ml_optimization(self) -> None:
        self._assert_page_runs_cleanly("pages/5_ML_and_Optimization.py", timeout=45.0)

    def test_page6_glossary(self) -> None:
        self._assert_page_runs_cleanly("pages/6_Glossary_and_Physics_Guide.py")

    def test_page7_fab_cycle_and_progression(self) -> None:
        page_path = APP_DIR / "pages/7_Fab_Cycle_and_Yield_Report.py"
        self.assertTrue(page_path.exists())
        at = AppTest.from_file(str(page_path), default_timeout=45.0)
        at.run()
        self.assertEqual(len(at.exception), 0, f"Initial load exception: {[e.message for e in at.exception]}")

        # Click '단계별 조치 반영 + 2차 실행' and then 3차 실행
        step_btn = next(b for b in at.button if "단계별 조치 반영" in b.label)
        step_btn.click().run()
        self.assertEqual(len(at.exception), 0, f"Cycle 2 exception: {[e.message for e in at.exception]}")

        step_btn2 = next(b for b in at.button if "단계별 조치 반영" in b.label)
        step_btn2.click().run()
        self.assertEqual(len(at.exception), 0, f"Cycle 3 exception: {[e.message for e in at.exception]}")

        # Cumulative table should now have 3 cycles
        self.assertEqual(len(at.dataframe[0].value), 3)


if __name__ == "__main__":
    unittest.main()
