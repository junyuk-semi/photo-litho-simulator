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


if __name__ == "__main__":
    unittest.main()
