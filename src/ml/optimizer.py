"""Stage 6: Surrogate-assisted, physics-verified optimal photolithography recipe search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from src.physics.constants import EXPOSURE_NODES
from src.physics.exposure_fem import simulate_fem
from src.physics.optics_tmm import (
    build_litho_stack,
    get_ambient_for_node,
    optimize_barc_thickness,
    simulate_multilayer_optics,
)
from src.physics.process_models import tier2_process_shift


@dataclass(frozen=True)
class OptimizationResult:
    """Ranked optimal process recipes verified by the physics engine."""

    node_key: str
    target_cd_nm: float
    underlayer: str
    illumination: str
    pattern: str
    best_recipe: Dict[str, object]
    candidates_df: pd.DataFrame
    rationale: str


def optimize_process_conditions(
    node_key: str = "ArFi_193",
    target_cd_nm: Optional[float] = None,
    underlayer: str = "Al_Metal",
    illumination: str = "Annular",
    pattern: str = "Dense_1to1",
    surrogate_model: Optional[Pipeline] = None,
    n_candidates: int = 1200,
    top_k_verify: int = 8,
    seed: int = 42,
) -> OptimizationResult:
    """Search optimal (BARC, PR thickness, PEB Temp, Dev Time, Dose, Focus) for max Process Window.

    Step 1: Determine optical BARC optimum via TMM for the target underlayer.
    Step 2: Screen candidate recipes with ML surrogate (if provided) or Sobol/random sampling.
    Step 3: Verify top candidates through full Optics-Coupled FEM to maximize PW Area while
            hitting target CD and keeping defect risk minimal.
    """
    node = EXPOSURE_NODES[node_key]
    if node.comparison_only:
        raise ValueError(f"Comparison-only node '{node_key}' is not supported for DUV recipe optimization")

    t_cd = node.default_target_cd_nm if target_cd_nm is None else float(target_cd_nm)
    ambient = get_ambient_for_node(node_key)

    barc_opt = optimize_barc_thickness(
        wavelength_nm=node.wavelength_nm,
        ambient_material=ambient,
        pr_thickness_nm=node.default_pr_thickness_nm,
        underlayer_material=underlayer,
    )
    opt_barc_nm = float(barc_opt["optimal_barc_nm"])

    rng = np.random.default_rng(seed)
    cand = pd.DataFrame(
        {
            "wavelength_nm": np.full(n_candidates, node.wavelength_nm),
            "na": np.full(n_candidates, node.na_default),
            "exposure_dose_mj_cm2": rng.uniform(0.80 * node.nominal_dose_mj_cm2, 1.20 * node.nominal_dose_mj_cm2, n_candidates),
            "focus_nm": rng.uniform(-25.0, 25.0, n_candidates),
            "pr_thickness_nm": rng.uniform(
                max(70.0, node.default_pr_thickness_nm - 18.0),
                node.default_pr_thickness_nm + 18.0,
                n_candidates,
            ),
            "barc_thickness_nm": np.clip(rng.normal(opt_barc_nm, 6.0, n_candidates), 0.0, 140.0),
            "peb_temp_c": rng.uniform(111.0, 119.0, n_candidates),
            "soft_bake_temp_c": rng.uniform(100.0, 110.0, n_candidates),
            "dev_time_s": rng.uniform(50.0, 70.0, n_candidates),
            "dev_conc_wt_pct": np.full(n_candidates, 2.38),
            "hmds_score": np.full(n_candidates, 1.0),
            "underlayer": [underlayer] * n_candidates,
            "illumination": [illumination] * n_candidates,
            "pattern": [pattern] * n_candidates,
        }
    )
    cand["abs_focus_nm"] = np.abs(cand["focus_nm"])

    # Attach inline optical metrology features (reflectance, eta_abs) via fast TMM evaluation at opt BARC
    opt_stack = build_litho_stack(
        wavelength_nm=node.wavelength_nm,
        ambient_material=ambient,
        pr_thickness_nm=node.default_pr_thickness_nm,
        barc_thickness_nm=opt_barc_nm,
        underlayer_material=underlayer,
    )
    opt_optics = simulate_multilayer_optics(opt_stack, node.wavelength_nm, n_z_points=40)
    cand["reflectance"] = np.full(n_candidates, opt_optics.reflectance)
    cand["eta_abs"] = np.full(n_candidates, opt_optics.effective_dose_factor)

    if surrogate_model is not None:
        pred_cd = surrogate_model.predict(cand)
        # Prioritize candidates close to target CD and near optical BARC optimum
        cand["surrogate_cd_nm"] = pred_cd
        cand["screen_score"] = (
            np.abs(pred_cd - t_cd)
            + 0.15 * np.abs(cand["barc_thickness_nm"] - opt_barc_nm)
            + 0.05 * cand["abs_focus_nm"]
        )
        shortlist = cand.nsmallest(top_k_verify, "screen_score")
    else:
        cand["screen_score"] = (
            np.abs(cand["barc_thickness_nm"] - opt_barc_nm)
            + 0.2 * np.abs(cand["pr_thickness_nm"] - node.default_pr_thickness_nm)
            + 0.4 * np.abs(cand["peb_temp_c"] - 115.0)
        )
        shortlist = cand.nsmallest(top_k_verify, "screen_score")

    verified_rows: List[Dict[str, object]] = []
    for _, row in shortlist.iterrows():
        t2 = tier2_process_shift(
            soft_bake_temp_c=float(row["soft_bake_temp_c"]),
            peb_temp_c=float(row["peb_temp_c"]),
            dev_time_s=float(row["dev_time_s"]),
            dev_conc_wt_pct=float(row["dev_conc_wt_pct"]),
            target_cd_nm=t_cd,
        )
        fem = simulate_fem(
            node_key=node_key,
            illumination=illumination,
            pattern=pattern,
            pr_thickness_nm=float(row["pr_thickness_nm"]),
            barc_thickness_nm=float(row["barc_thickness_nm"]),
            underlayer_material=underlayer,
            target_cd_nm=t_cd,
            n_dose=27,
            n_focus=33,
            process_cd_bias_nm=t2["process_cd_bias_nm"],
            contrast_modifier=t2["contrast_modifier"],
            hmds_score=1.0,
            soft_bake_temp_c=float(row["soft_bake_temp_c"]),
        )
        pw = fem.process_window
        defects = fem.defects_at_center
        # Composite engineering objective: maximize PW Area, penalize defect risk and substrate reflectance
        obj_score = pw.pw_area - 15.0 * defects.overall_defect_risk - 800.0 * fem.optics.substrate_reflectance

        verified_rows.append(
            {
                "Optimal Dose (mJ/cm²)": round(pw.best_dose_mj_cm2, 2),
                "Optimal Focus (nm)": round(pw.best_focus_nm, 1),
                "PR Thickness (nm)": round(float(row["pr_thickness_nm"]), 1),
                "BARC Thickness (nm)": round(float(row["barc_thickness_nm"]), 1),
                "PEB Temp (°C)": round(float(row["peb_temp_c"]), 2),
                "Dev Time (s)": round(float(row["dev_time_s"]), 1),
                "R_sub (%)": round(fem.optics.substrate_reflectance * 100.0, 2),
                "PW DOF (nm)": round(pw.pw_dof_nm, 1),
                "PW EL (%)": round(pw.pw_el_pct, 2),
                "PW Area": round(pw.pw_area, 1),
                "Defect Risk": round(defects.overall_defect_risk, 1),
                "Score": round(obj_score, 1),
            }
        )

    verified_df = pd.DataFrame(verified_rows).sort_values("Score", ascending=False).reset_index(drop=True)
    best = verified_df.iloc[0].to_dict()
    rationale = (
        f"[{node_key} / {underlayer} / {illumination} / {pattern}] "
        f"TMM 최적 BARC({opt_barc_nm:.1f} nm) 인근에서 하부 반사율 R_sub={best['R_sub (%)']}%로 억제하고, "
        f"목표 CD={t_cd:.1f} nm 기준 최대 내접 Process Window(DOF={best['PW DOF (nm)']} nm @ EL={best['PW EL (%)']}%, "
        f"Defect Risk={best['Defect Risk']})를 달성하는 조건을 물리 엔진으로 최종 검증 선정함."
    )
    return OptimizationResult(
        node_key=node_key,
        target_cd_nm=t_cd,
        underlayer=underlayer,
        illumination=illumination,
        pattern=pattern,
        best_recipe=best,
        candidates_df=verified_df,
        rationale=rationale,
    )
