"""Real-world Fab Photolithography Flow, Run-to-Run Cycle Engine & Engineering Report Generator.

Simulates the sequential industrial workflow:
  Upstream (Thin Film & CMP) -> Photo Track (HMDS, BARC, Spin Coat, Soft Bake)
  -> Scanner (Exposure & Focus APC) -> Post-Exposure Bake & Develop (PEB, TMAH, Hard Bake)
  -> ADI Metrology -> Downstream (Etch Bias & ACI Yield) -> Root-Cause Data Analysis & CAPA Report.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.data.analysis import run_ols_regression
from src.physics.constants import DEFECT_THRESHOLDS, EXPOSURE_NODES
from src.physics.exposure_fem import (
    DefectAssessment,
    FEMResult,
    aerial_image_contrast,
    bossung_cd,
    evaluate_defects,
    simulate_fem,
)
from src.physics.optics_tmm import (
    OpticalStackResult,
    build_litho_stack,
    get_ambient_for_node,
    optimize_barc_thickness,
    simulate_multilayer_optics,
)
from src.physics.process_models import (
    WaferCDUResult,
    spin_coating_thickness_nm,
    tier2_process_shift,
)
from src.physics.resolution import depth_of_focus, rayleigh_resolution


@dataclass(frozen=True)
class FabRecipe:
    """Complete sequential semiconductor photolithography recipe across upstream/photo/etch."""

    # 1. Upstream Thin Film & CMP
    node_key: str = "ArFi_193"
    underlayer_material: str = "Al_Metal"
    underlayer_thickness_nm: float = 100.0
    cmp_dishing_defocus_nm: float = 35.0
    cmp_focus_sigma_nm: float = 24.0

    # 2. Photo Track Front (HMDS, BARC, Spin Coating)
    hmds_score: float = 0.6
    barc_thickness_nm: float = 0.0
    spin_speed_rpm: float = 1750.0
    pr_viscosity_cp: float = 3.0
    dispense_volume_ml: float = 1.2
    pr_radial_range_nm: float = 6.5

    # 3. Bake (Soft Bake & PEB)
    soft_bake_temp_c: float = 108.0
    peb_temp_c: float = 115.0
    peb_radial_range_c: float = 1.6

    # 4. Scanner (Optics & Exposure)
    na: float = 1.35
    illumination: str = "Annular"
    pattern: str = "Dense_1to1"
    exposure_dose_mj_cm2: float = 23.0
    focus_offset_nm: float = 0.0
    dose_noise_sigma_pct: float = 1.6

    # 5. Develop & Hard Bake
    dev_time_s: float = 60.0
    dev_conc_wt_pct: float = 2.38
    hard_bake_temp_c: float = 125.0

    # 6. Downstream Etch & ACI Spec
    target_aci_cd_nm: float = 45.0
    etch_bias_nm: float = -2.0
    min_pr_for_etch_nm: float = 85.0


@dataclass(frozen=True)
class ActionItem:
    """Concrete Corrective and Preventive Action (CAPA) derived from cycle data analysis."""

    priority: str  # "P1 (긴급)" | "P2 (중요)" | "P3 (미세조정)"
    stage: str
    issue: str
    action: str
    expected_effect: str
    updates: Dict[str, object]


@dataclass(frozen=True)
class CycleResult:
    """Full simulation output, statistical root-cause diagnosis & engineering report for one cycle."""

    cycle_id: int
    label: str
    recipe: FabRecipe
    pr_thickness_nm: float
    target_adi_cd_nm: float
    target_aci_cd_nm: float
    min_cd_nm: float
    dof_high_na_nm: float
    optics: OpticalStackResult
    optimal_barc_nm: float
    min_barc_reflectance: float
    fem: FEMResult
    defects_operating: DefectAssessment
    wafer_cdu: WaferCDUResult
    aci_cd_sites_nm: np.ndarray
    aci_mean_cd_nm: float
    aci_cdu_3sigma_nm: float
    aci_cdu_3sigma_pct: float
    adi_yield_pct: float
    aci_yield_pct: float
    cd_bias_error_nm: float
    etch_pr_margin_nm: float
    variance_breakdown: List[Dict[str, object]]
    ols_top_drivers: List[Dict[str, object]]
    action_items: List[ActionItem]
    recommended_stepwise_recipe: FabRecipe
    recommended_full_recipe: FabRecipe
    report_markdown: str


def preset_recipes(node_key: str = "ArFi_193") -> Dict[str, FabRecipe]:
    """Return realistic starting scenario presets for Run-to-Run Fab simulation."""
    node = EXPOSURE_NODES[node_key]
    if node.comparison_only:
        raise ValueError(f"Comparison-only node '{node_key}' is not supported for DUV Fab cycles")

    base_dose = node.nominal_dose_mj_cm2
    base_cd = node.default_target_cd_nm
    # Calibrate spin RPM roughly to node's default PR thickness
    rpm_nom = 3000.0 * (120.0 / node.default_pr_thickness_nm) ** 2
    rpm_nom = float(np.clip(rpm_nom, 1200.0, 5500.0))

    return {
        "1차 초기 불량 시나리오 (Al 금속배선 · BARC 미적용)": FabRecipe(
            node_key=node_key,
            underlayer_material="Al_Metal",
            underlayer_thickness_nm=100.0,
            cmp_dishing_defocus_nm=55.0,
            cmp_focus_sigma_nm=32.0,
            hmds_score=0.6,
            barc_thickness_nm=0.0,
            spin_speed_rpm=round(max(1200.0, rpm_nom * 0.62), 0),
            pr_viscosity_cp=3.0,
            dispense_volume_ml=1.1,
            pr_radial_range_nm=7.5,
            soft_bake_temp_c=108.0,
            peb_temp_c=115.0,
            peb_radial_range_c=2.4,
            na=node.na_default,
            illumination="Conventional",
            pattern="Dense_1to1",
            exposure_dose_mj_cm2=round(base_dose * 0.50, 1),
            focus_offset_nm=0.0,
            dose_noise_sigma_pct=2.2,
            dev_time_s=60.0,
            dev_conc_wt_pct=2.38,
            hard_bake_temp_c=125.0,
            target_aci_cd_nm=base_cd,
            etch_bias_nm=-2.0 if base_cd <= 90.0 else -4.0,
            min_pr_for_etch_nm=round(node.default_pr_thickness_nm * 0.70, 1),
        ),
        "CMP 단차 & 열불균형 불량 시나리오 (Poly-Si 게이트)": FabRecipe(
            node_key=node_key,
            underlayer_material="PolySi",
            underlayer_thickness_nm=120.0,
            cmp_dishing_defocus_nm=-45.0,
            cmp_focus_sigma_nm=28.0,
            hmds_score=1.0,
            barc_thickness_nm=12.0,
            spin_speed_rpm=round(rpm_nom, 0),
            pr_viscosity_cp=3.0,
            dispense_volume_ml=1.4,
            pr_radial_range_nm=5.5,
            soft_bake_temp_c=105.0,
            peb_temp_c=118.0,
            peb_radial_range_c=1.8,
            na=node.na_default,
            illumination="Annular",
            pattern="Dense_1to1",
            exposure_dose_mj_cm2=round(base_dose * 1.12, 1),
            focus_offset_nm=0.0,
            dose_noise_sigma_pct=1.4,
            dev_time_s=60.0,
            dev_conc_wt_pct=2.38,
            hard_bake_temp_c=125.0,
            target_aci_cd_nm=base_cd,
            etch_bias_nm=-2.0 if base_cd <= 90.0 else -4.0,
            min_pr_for_etch_nm=round(node.default_pr_thickness_nm * 0.70, 1),
        ),
        "표준 기준선 레시피 (Baseline)": FabRecipe(
            node_key=node_key,
            underlayer_material="SiO2",
            underlayer_thickness_nm=100.0,
            cmp_dishing_defocus_nm=0.0,
            cmp_focus_sigma_nm=10.0,
            hmds_score=1.0,
            barc_thickness_nm=30.0,
            spin_speed_rpm=round(rpm_nom, 0),
            pr_viscosity_cp=3.0,
            dispense_volume_ml=2.2,
            pr_radial_range_nm=2.2,
            soft_bake_temp_c=105.0,
            peb_temp_c=115.0,
            peb_radial_range_c=0.4,
            na=node.na_default,
            illumination="Annular",
            pattern="Dense_1to1",
            exposure_dose_mj_cm2=base_dose,
            focus_offset_nm=0.0,
            dose_noise_sigma_pct=0.7,
            dev_time_s=60.0,
            dev_conc_wt_pct=2.38,
            hard_bake_temp_c=125.0,
            target_aci_cd_nm=base_cd,
            etch_bias_nm=-2.0 if base_cd <= 90.0 else -4.0,
            min_pr_for_etch_nm=round(node.default_pr_thickness_nm * 0.70, 1),
        ),
    }


def _solve_dose_for_target_adi(
    target_adi_cd_nm: float,
    nominal_dose_mj_cm2: float,
    dof_scale_nm: float,
    eta_abs: float,
    pattern: str,
    illumination: str,
    process_cd_bias_nm: float,
    contrast_modifier: float,
) -> float:
    """Solve exact exposure dose hitting target_adi_cd_nm at zero effective defocus."""
    lo, hi = 0.25 * nominal_dose_mj_cm2, 3.0 * nominal_dose_mj_cm2
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        cd_mid = float(
            bossung_cd(
                mid,
                0.0,
                target_cd_nm=target_adi_cd_nm,
                nominal_dose_mj_cm2=nominal_dose_mj_cm2,
                dof_scale_nm=dof_scale_nm,
                effective_dose_factor=eta_abs,
                pattern=pattern,
                illumination=illumination,
                best_focus_nm=0.0,
                process_cd_bias_nm=process_cd_bias_nm,
                contrast_modifier=contrast_modifier,
            )
        )
        # Positive PR: higher dose -> smaller CD
        if cd_mid > target_adi_cd_nm:
            lo = mid
        else:
            hi = mid
    return round(0.5 * (lo + hi), 2)


def _compute_wafer_sites(
    recipe: FabRecipe,
    pr_thickness_nm: float,
    target_adi_cd_nm: float,
    dof_scale_nm: float,
    t2_nominal: Dict[str, float],
    seed: int,
) -> Tuple[WaferCDUResult, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Evaluate 300mm wafer site-by-site ADI & ACI CDs plus intermediate physical arrays."""
    node = EXPOSURE_NODES[recipe.node_key]
    rng = np.random.default_rng(seed)

    coords = np.linspace(-135.0, 135.0, 19)
    xx, yy = np.meshgrid(coords, coords)
    rr = np.sqrt(xx**2 + yy**2)
    mask = rr <= 142.0
    x_mm = xx[mask]
    y_mm = yy[mask]
    r_mm = rr[mask]
    r_norm = r_mm / 145.0
    theta = np.arctan2(y_mm, x_mm)
    n_sites = x_mm.size

    coat_factor = 1.0 + max(0.0, 1.5 - recipe.dispense_volume_ml) * 0.8
    pr_site = pr_thickness_nm + coat_factor * recipe.pr_radial_range_nm * (r_norm**2 - 0.5) + rng.normal(0.0, 0.35, n_sites)
    pr_site = np.maximum(pr_site, 20.0)

    peb_site = (
        recipe.peb_temp_c
        + recipe.peb_radial_range_c * (0.5 - r_norm**2)
        + 0.20 * recipe.peb_radial_range_c * r_norm * np.cos(theta - 0.7)
        + rng.normal(0.0, 0.08, n_sites)
    )

    # Effective focus = Scanner offset + Upstream CMP dishing residual + CMP/Scanner focus scatter
    mean_focus = recipe.focus_offset_nm + recipe.cmp_dishing_defocus_nm
    focus_site = mean_focus + rng.normal(0.0, recipe.cmp_focus_sigma_nm, n_sites)
    dose_site = recipe.exposure_dose_mj_cm2 * (1.0 + rng.normal(0.0, recipe.dose_noise_sigma_pct / 100.0, n_sites))
    dose_site = np.maximum(dose_site, 1.0)
    metrology_noise = rng.normal(0.0, 0.35, n_sites)

    ambient = get_ambient_for_node(recipe.node_key)
    pr_lut = np.linspace(float(np.min(pr_site)) - 1.0, float(np.max(pr_site)) + 1.0, 25)
    eta_lut = np.empty_like(pr_lut)
    for i, d_val in enumerate(pr_lut):
        st = build_litho_stack(
            wavelength_nm=node.wavelength_nm,
            ambient_material=ambient,
            pr_thickness_nm=float(d_val),
            barc_thickness_nm=recipe.barc_thickness_nm,
            underlayer_material=recipe.underlayer_material,
            underlayer_thickness_nm=recipe.underlayer_thickness_nm,
        )
        eta_lut[i] = simulate_multilayer_optics(st, node.wavelength_nm, n_z_points=60).effective_dose_factor
    eta_site = np.interp(pr_site, pr_lut, eta_lut)

    cd_adi = np.empty(n_sites)
    for i in range(n_sites):
        t2_i = tier2_process_shift(
            soft_bake_temp_c=recipe.soft_bake_temp_c,
            peb_temp_c=float(peb_site[i]),
            hard_bake_temp_c=recipe.hard_bake_temp_c,
            dev_time_s=recipe.dev_time_s,
            dev_conc_wt_pct=recipe.dev_conc_wt_pct,
            target_cd_nm=target_adi_cd_nm,
        )
        val = float(
            bossung_cd(
                float(dose_site[i]),
                float(focus_site[i]),
                target_cd_nm=target_adi_cd_nm,
                nominal_dose_mj_cm2=node.nominal_dose_mj_cm2,
                dof_scale_nm=dof_scale_nm,
                effective_dose_factor=float(eta_site[i]),
                pattern=recipe.pattern,
                illumination=recipe.illumination,
                best_focus_nm=0.0,
                process_cd_bias_nm=t2_i["process_cd_bias_nm"],
                contrast_modifier=t2_i["contrast_modifier"],
            )
        )
        cd_adi[i] = max(0.0, val + float(metrology_noise[i]))

    mean_adi = float(np.mean(cd_adi))
    std_adi = float(np.std(cd_adi, ddof=1))
    cdu_3s = 3.0 * std_adi
    cdu_pct = 100.0 * cdu_3s / max(target_adi_cd_nm, 1e-6)
    tol_adi = target_adi_cd_nm * DEFECT_THRESHOLDS["cd_spec_tolerance_ratio"]
    adi_yield = float(100.0 * np.mean(np.abs(cd_adi - target_adi_cd_nm) <= tol_adi))

    cdu_res = WaferCDUResult(
        node_key=recipe.node_key,
        target_cd_nm=target_adi_cd_nm,
        x_mm=x_mm,
        y_mm=y_mm,
        radius_mm=r_mm,
        pr_thickness_nm=pr_site,
        peb_temp_c=peb_site,
        cd_nm=cd_adi,
        mean_cd_nm=mean_adi,
        std_cd_nm=std_adi,
        cdu_3sigma_nm=cdu_3s,
        cdu_3sigma_pct=cdu_pct,
        within_spec_yield_pct=adi_yield,
    )
    return cdu_res, focus_site, dose_site, eta_site, metrology_noise, t2_nominal


def _decompose_error_sources(
    recipe: FabRecipe,
    pr_thickness_nm: float,
    target_adi_cd_nm: float,
    dof_scale_nm: float,
    optics_center: OpticalStackResult,
    cdu_res: WaferCDUResult,
    focus_site: np.ndarray,
    dose_site: np.ndarray,
    eta_site: np.ndarray,
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """Quantify each process source's contribution to wafer CD error (RMS deviation from target)."""
    node = EXPOSURE_NODES[recipe.node_key]
    n_sites = cdu_res.cd_nm.size
    t2_nom = tier2_process_shift(
        soft_bake_temp_c=recipe.soft_bake_temp_c,
        peb_temp_c=recipe.peb_temp_c,
        hard_bake_temp_c=recipe.hard_bake_temp_c,
        dev_time_s=recipe.dev_time_s,
        dev_conc_wt_pct=recipe.dev_conc_wt_pct,
        target_cd_nm=target_adi_cd_nm,
    )

    def _eval_rms(d_arr: np.ndarray, f_arr: np.ndarray, eta_arr: np.ndarray, peb_arr: np.ndarray) -> float:
        vals = np.empty(n_sites)
        for i in range(n_sites):
            t2_i = tier2_process_shift(
                soft_bake_temp_c=recipe.soft_bake_temp_c,
                peb_temp_c=float(peb_arr[i]),
                hard_bake_temp_c=recipe.hard_bake_temp_c,
                dev_time_s=recipe.dev_time_s,
                dev_conc_wt_pct=recipe.dev_conc_wt_pct,
                target_cd_nm=target_adi_cd_nm,
            )
            vals[i] = float(
                bossung_cd(
                    float(d_arr[i]),
                    float(f_arr[i]),
                    target_cd_nm=target_adi_cd_nm,
                    nominal_dose_mj_cm2=node.nominal_dose_mj_cm2,
                    dof_scale_nm=dof_scale_nm,
                    effective_dose_factor=float(eta_arr[i]),
                    pattern=recipe.pattern,
                    illumination=recipe.illumination,
                    best_focus_nm=0.0,
                    process_cd_bias_nm=t2_i["process_cd_bias_nm"],
                    contrast_modifier=t2_i["contrast_modifier"],
                )
            )
        return float(np.sqrt(np.mean((vals - target_adi_cd_nm) ** 2)))

    # Isolated marginal RMS error when ONLY one factor varies from ideal target state
    dose_ideal = _solve_dose_for_target_adi(
        target_adi_cd_nm,
        node.nominal_dose_mj_cm2,
        dof_scale_nm,
        optics_center.effective_dose_factor,
        recipe.pattern,
        recipe.illumination,
        t2_nom["process_cd_bias_nm"],
        t2_nom["contrast_modifier"],
    )
    dose_flat = np.full(n_sites, recipe.exposure_dose_mj_cm2)
    dose_ideal_arr = np.full(n_sites, dose_ideal)
    focus_zero = np.zeros(n_sites)
    eta_flat = np.full(n_sites, optics_center.effective_dose_factor)
    peb_flat = np.full(n_sites, recipe.peb_temp_c)

    # Individual physical error factors (nm RMS)
    err_dose_bias = _eval_rms(dose_flat, focus_zero, eta_flat, peb_flat)
    err_cmp_focus = _eval_rms(dose_ideal_arr, focus_site, eta_flat, peb_flat)
    err_coat_swing = _eval_rms(dose_ideal_arr, focus_zero, eta_site, peb_flat)
    err_peb_grad = _eval_rms(dose_ideal_arr, focus_zero, eta_flat, cdu_res.peb_temp_c)
    err_shot_dose = _eval_rms(dose_site * (dose_ideal / max(recipe.exposure_dose_mj_cm2, 1e-6)), focus_zero, eta_flat, peb_flat)

    raw_items = [
        ("평균 Dose / Etch Bias 타겟 오프셋", err_dose_bias, "노광기 Dose 또는 PEB/현상 타겟이 Etch Bias 감안 ADI 목표에서 이탈"),
        ("CMP 단차 & Focus 산포", err_cmp_focus, "전 공정 CMP 디싱 잔여 Defocus 및 샷별 Focus 흔들림"),
        ("PR 코팅 편차 × 박막 Swing 간섭", err_coat_swing, "스핀 코팅 반경 두께 편차가 하부 반사 간섭(η_abs)을 통해 유효 광량 흔듦"),
        ("PEB 핫플레이트 온도 구배", err_peb_grad, "웨이퍼 중심-가장자리 온도 편차로 인한 Arrhenius 산 확산 거리 차이"),
        ("스캐너 샷 Dose 노이즈", err_shot_dose, "노광 샷별 광량 산포"),
    ]
    total_sq = sum(x[1] ** 2 for x in raw_items)
    breakdown: List[Dict[str, object]] = []
    for name, rms_val, desc in raw_items:
        share_pct = 100.0 * (rms_val**2) / max(total_sq, 1e-12)
        breakdown.append(
            {
                "cause": name,
                "rms_error_nm": round(rms_val, 3),
                "variance_share_pct": round(share_pct, 1),
                "description": desc,
            }
        )
    breakdown.sort(key=lambda r: float(r["rms_error_nm"]), reverse=True)

    # Also compute within-wafer OLS standardized drivers for spatial CDU diagnostics
    site_df = pd.DataFrame(
        {
            "exposure_dose_mj_cm2": dose_site,
            "abs_focus_nm": np.abs(focus_site),
            "pr_thickness_nm": cdu_res.pr_thickness_nm,
            "peb_temp_c": cdu_res.peb_temp_c,
            "eta_abs": eta_site,
            "cd_measured_nm": cdu_res.cd_nm,
        }
    )
    ols = run_ols_regression(
        site_df,
        features=("exposure_dose_mj_cm2", "abs_focus_nm", "pr_thickness_nm", "peb_temp_c", "eta_abs"),
        target="cd_measured_nm",
    )
    coef_rows = ols.coefficients_df[ols.coefficients_df["feature"] != "intercept"].sort_values(
        "abs_std_beta", ascending=False
    )
    ols_drivers = [
        {
            "feature": str(r["feature"]),
            "std_beta": round(float(r["std_beta"]), 3),
            "p_value": float(r["p_value"]),
        }
        for _, r in coef_rows.iterrows()
    ]
    return breakdown, ols_drivers


def _diagnose_actions(
    recipe: FabRecipe,
    pr_thickness_nm: float,
    target_adi_cd_nm: float,
    dof_scale_nm: float,
    optics: OpticalStackResult,
    optimal_barc_nm: float,
    min_barc_refl: float,
    defects: DefectAssessment,
    cdu_res: WaferCDUResult,
    aci_yield_pct: float,
    t2_nom: Dict[str, float],
) -> Tuple[List[ActionItem], FabRecipe, FabRecipe]:
    """Generate prioritized CAPA action items plus stepwise and full next-cycle recipes."""
    node = EXPOSURE_NODES[recipe.node_key]
    actions: List[ActionItem] = []

    # 1. Optical BARC optimization
    barc_delta = abs(recipe.barc_thickness_nm - optimal_barc_nm)
    if optics.substrate_reflectance > 0.03 or barc_delta > 4.0:
        prio = "P1 (긴급)" if optics.substrate_reflectance > 0.10 else "P2 (중요)"
        actions.append(
            ActionItem(
                priority=prio,
                stage="광학 / BARC 코팅",
                issue=f"하부막({recipe.underlayer_material}) 반사율 R_sub={optics.substrate_reflectance*100:.1f}%, SWR={optics.swr_local:.2f}로 정상파 및 Reflective Notching 위험",
                action=f"BARC 두께를 {recipe.barc_thickness_nm:.1f} nm → TMM 최적 두께 **{optimal_barc_nm:.1f} nm**로 변경",
                expected_effect=f"하부 반사율 {optics.substrate_reflectance*100:.1f}% → {min_barc_refl*100:.2f}%로 억제, Swing 진폭 대폭 축소",
                updates={"barc_thickness_nm": round(optimal_barc_nm, 1)},
            )
        )

    # 2. HMDS & PR Thickness (Pattern Collapse / Etch Margin / Aspect Ratio)
    ar = pr_thickness_nm / max(target_adi_cd_nm, 1.0)
    desired_pr = float(np.clip(max(recipe.min_pr_for_etch_nm + 12.0, min(node.default_pr_thickness_nm, 2.55 * target_adi_cd_nm)), 65.0, 400.0))
    desired_rpm = round(
        float(np.clip(recipe.spin_speed_rpm * (pr_thickness_nm / desired_pr) ** 2, 1200.0, 6500.0)),
        0,
    )
    if recipe.hmds_score < 0.95 or ar > 2.85 or pr_thickness_nm < recipe.min_pr_for_etch_nm:
        coat_updates: Dict[str, object] = {}
        msgs: List[str] = []
        if recipe.hmds_score < 0.95:
            coat_updates["hmds_score"] = 1.0
            msgs.append("HMDS 표면처리를 Vapor(1.0)로 전환")
        if ar > 2.85 or pr_thickness_nm < recipe.min_pr_for_etch_nm:
            coat_updates["spin_speed_rpm"] = desired_rpm
            msgs.append(f"Spin Speed를 {recipe.spin_speed_rpm:.0f} → {desired_rpm:.0f} RPM으로 조정해 PR 두께를 {pr_thickness_nm:.1f} → ~{desired_pr:.1f} nm로 최적화")
        actions.append(
            ActionItem(
                priority="P1 (긴급)" if (ar > 3.0 or recipe.hmds_score < 0.5) else "P2 (중요)",
                stage="포토 전처리 & PR 코팅",
                issue=f"PR 두께={pr_thickness_nm:.1f} nm (AR={ar:.2f}), HMDS={recipe.hmds_score:.1f}로 패턴 붕괴(Collapse) 또는 식각 마진 부족 위험",
                action=" / ".join(msgs),
                expected_effect="PR 접착력 확보 및 종횡비(AR ≤ 2.6) 안정화 + 후속 Etch 내식각성 유지",
                updates=coat_updates,
            )
        )

    # 3. Illumination OAI upgrade for dense patterns if Conventional
    if recipe.pattern == "Dense_1to1" and recipe.illumination == "Conventional":
        actions.append(
            ActionItem(
                priority="P2 (중요)",
                stage="노광기 조명계 (OAI)",
                issue="Dense 1:1 패턴에서 Conventional 수직 조명을 사용해 유효 k1 및 DOF 여유가 제한됨",
                action="조명계 모드를 Conventional → **Annular OAI**로 전환",
                expected_effect="유효 k1 10% 개선 및 Dense 패턴 DOF ~25% 확장",
                updates={"illumination": "Annular"},
            )
        )

    # 4. Exposure Dose APC (accounting for optimal BARC eta_abs & Etch Bias!)
    next_barc = float(optimal_barc_nm if (optics.substrate_reflectance > 0.03 or barc_delta > 4.0) else recipe.barc_thickness_nm)
    next_pr = float(desired_pr if (ar > 2.85 or pr_thickness_nm < recipe.min_pr_for_etch_nm) else pr_thickness_nm)
    next_illum = "Annular" if (recipe.pattern == "Dense_1to1" and recipe.illumination == "Conventional") else recipe.illumination
    ambient = get_ambient_for_node(recipe.node_key)
    next_stack = build_litho_stack(
        wavelength_nm=node.wavelength_nm,
        ambient_material=ambient,
        pr_thickness_nm=next_pr,
        barc_thickness_nm=next_barc,
        underlayer_material=recipe.underlayer_material,
        underlayer_thickness_nm=recipe.underlayer_thickness_nm,
    )
    next_optics = simulate_multilayer_optics(next_stack, node.wavelength_nm, n_z_points=60)
    next_dof = float(
        depth_of_focus(
            node.wavelength_nm,
            recipe.na,
            k2=node.k2_default,
            n_fluid=node.n_fluid,
            illumination=next_illum,
            pattern=recipe.pattern,
            high_na=True,
        )
    )
    target_dose = _solve_dose_for_target_adi(
        target_adi_cd_nm,
        node.nominal_dose_mj_cm2,
        next_dof,
        next_optics.effective_dose_factor,
        recipe.pattern,
        next_illum,
        t2_nom["process_cd_bias_nm"],
        t2_nom["contrast_modifier"],
    )
    cd_bias = cdu_res.mean_cd_nm - target_adi_cd_nm
    if abs(cd_bias) > 0.8 or abs(recipe.exposure_dose_mj_cm2 - target_dose) > 0.6:
        actions.append(
            ActionItem(
                priority="P1 (긴급)" if abs(cd_bias) > 2.5 else "P2 (중요)",
                stage="노광기 Dose APC",
                issue=f"평균 ADI CD={cdu_res.mean_cd_nm:.2f} nm (목표 {target_adi_cd_nm:.1f} nm 대비 {cd_bias:+.2f} nm 이탈, Etch Bias={recipe.etch_bias_nm:+.1f} nm 반영)",
                action=f"Exposure Dose를 {recipe.exposure_dose_mj_cm2:.1f} → **{target_dose:.2f} mJ/cm²**로 APC 보정 (변경될 광학 η_abs={next_optics.effective_dose_factor:.3f} 반영)",
                expected_effect=f"평균 ACI CD를 목표 {recipe.target_aci_cd_nm:.1f} nm 중앙으로 정렬",
                updates={"exposure_dose_mj_cm2": target_dose},
            )
        )

    # 5. Upstream CMP Dishing Focus APC & CMP Focus Sigma
    mean_eff_focus = recipe.focus_offset_nm + recipe.cmp_dishing_defocus_nm
    target_focus_offset = round(-recipe.cmp_dishing_defocus_nm, 1)
    if abs(mean_eff_focus) > 6.0:
        actions.append(
            ActionItem(
                priority="P1 (긴급)" if abs(mean_eff_focus) > 20.0 else "P2 (중요)",
                stage="노광기 Focus APC (CMP 연동)",
                issue=f"전 공정 CMP 디싱({recipe.cmp_dishing_defocus_nm:+.1f} nm)으로 인해 실효 평균 Focus가 {mean_eff_focus:+.1f} nm 이탈",
                action=f"스캐너 Focus Offset을 {recipe.focus_offset_nm:+.1f} → **{target_focus_offset:+.1f} nm**로 Feed-Forward 보정",
                expected_effect="실효 Focus 중심을 Best Focus(0 nm)로 복원해 Bossung 좌우 편차 제거",
                updates={"focus_offset_nm": target_focus_offset},
            )
        )

    # 6. Wafer Uniformity & Scatter Reduction (Spin Coating / PEB Hotplate / CMP Sigma / Scanner)
    if recipe.pr_radial_range_nm > 3.0 or recipe.dispense_volume_ml < 1.8:
        actions.append(
            ActionItem(
                priority="P2 (중요)" if cdu_res.cdu_3sigma_pct > 5.0 else "P3 (미세조정)",
                stage="트랙 코팅 균일도 (CDU)",
                issue=f"PR 반경 두께 편차({recipe.pr_radial_range_nm:.1f} nm) 및 토출량({recipe.dispense_volume_ml:.1f} mL) 부족으로 에지 CD 산포 증가",
                action=f"Dispense Volume {recipe.dispense_volume_ml:.1f} → **2.2 mL** 상향 및 스핀 레시피 튜닝으로 반경 편차 → **2.0 nm** 이내 제어",
                expected_effect="웨이퍼 센터-에지 코팅 균일도 개선 및 Swing 유도 CD 편차 축소",
                updates={"dispense_volume_ml": 2.2, "pr_radial_range_nm": 2.0},
            )
        )

    if recipe.peb_radial_range_c > 0.6:
        actions.append(
            ActionItem(
                priority="P2 (중요)" if recipe.peb_radial_range_c > 1.0 else "P3 (미세조정)",
                stage="트랙 PEB 핫플레이트",
                issue=f"PEB 핫플레이트 면내 온도 편차(±{recipe.peb_radial_range_c:.1f} °C)로 인한 Arrhenius 산 확산 불균일",
                action=f"멀티존 핫플레이트 보정으로 PEB 온도 편차를 {recipe.peb_radial_range_c:.1f} → **0.4 °C** 이하로 튜닝",
                expected_effect="웨이퍼 면내 CDU 3σ 대폭 감소 (열 구배 제거)",
                updates={"peb_radial_range_c": 0.4},
            )
        )

    if recipe.cmp_focus_sigma_nm > 12.0 or recipe.dose_noise_sigma_pct > 0.9:
        actions.append(
            ActionItem(
                priority="P2 (중요)" if recipe.cmp_focus_sigma_nm > 18.0 else "P3 (미세조정)",
                stage="전공정 CMP · 스캐너 안정화",
                issue=f"CMP 단차 산포(σ_focus={recipe.cmp_focus_sigma_nm:.1f} nm) 또는 스캐너 Dose 산포({recipe.dose_noise_sigma_pct:.1f}%)가 공정 창을 잠식",
                action=f"CMP 평탄화 개선(σ_focus → **9.0 nm**) 및 스캐너 샷 Dose 안정화(→ **0.6%**)",
                expected_effect="고디포커스/고도즈 아웃라이어 칩 제거로 수율 ≥ 98% 달성",
                updates={"cmp_focus_sigma_nm": 9.0, "dose_noise_sigma_pct": 0.6},
            )
        )

    # Build full recipe (apply all actions)
    full_updates: Dict[str, object] = {}
    for act in actions:
        full_updates.update(act.updates)
    full_recipe = replace(recipe, **full_updates) if full_updates else recipe

    # Build realistic stepwise Run-to-Run recipe:
    # Phase A (urgent optical/collapse/coarse dose) if optical reflection or collapse or large bias exists;
    # Phase B (precision APC + uniformity/scatter tuning) once optics & basic film are stabilized.
    step_updates: Dict[str, object] = {}
    has_optical_or_film_issue = (
        optics.substrate_reflectance > 0.05
        or abs(recipe.barc_thickness_nm - optimal_barc_nm) > 5.0
        or recipe.hmds_score < 0.95
        or ar > 2.85
    )
    if has_optical_or_film_issue:
        # Cycle 1 -> 2: fix optical BARC, HMDS/PR thickness, and Dose APC matching the new BARC eta_abs
        # (leave CMP Focus APC, OAI, and Coat/PEB/CMP scatter tuning for Cycle 2 -> 3)
        for act in actions:
            if act.stage in ("광학 / BARC 코팅", "포토 전처리 & PR 코팅", "노광기 Dose APC"):
                step_updates.update(act.updates)
    else:
        # Cycle 2 -> 3+: fine APC (exact Dose + CMP Focus compensation + OAI) and track/CMP uniformity scatter reduction
        step_updates.update(full_updates)

    stepwise_recipe = replace(recipe, **step_updates) if step_updates else full_recipe
    return actions, stepwise_recipe, full_recipe


def _build_cycle_report_markdown(
    cycle_id: int,
    label: str,
    recipe: FabRecipe,
    pr_thickness_nm: float,
    target_adi_cd_nm: float,
    optics: OpticalStackResult,
    optimal_barc_nm: float,
    fem: FEMResult,
    defects: DefectAssessment,
    cdu: WaferCDUResult,
    aci_mean: float,
    aci_3s: float,
    aci_yield: float,
    etch_pr_margin: float,
    breakdown: List[Dict[str, object]],
    ols_drivers: List[Dict[str, object]],
    actions: List[ActionItem],
) -> str:
    """Create a structured Korean engineering report with data analysis and next CAPA actions."""
    pw = fem.process_window
    status_badge = "PASS (양산 적합)" if (aci_yield >= 95.0 and defects.overall_defect_risk < 25.0) else (
        "WARNING (추가 튜닝 필요)" if aci_yield >= 70.0 else "FAIL (긴급 공정 개선 필요)"
    )

    lines = [
        f"## 📋 {cycle_id}차 시뮬레이션 공정 결과 및 데이터 분석 보고서 — {label}",
        "",
        f"- **종합 판정**: `{status_badge}` | **최종 ACI 웨이퍼 수율**: **{aci_yield:.1f}%** (ADI 수율: {cdu.within_spec_yield_pct:.1f}%)",
        f"- **공정 조건 요약**: `{recipe.node_key}` (`NA={recipe.na:.2f}`, `{recipe.illumination}`, `{recipe.pattern}`) | 하부막 `{recipe.underlayer_material} ({recipe.underlayer_thickness_nm:.0f} nm)` | CMP 단차 Defocus `{recipe.cmp_dishing_defocus_nm:+.1f} nm (σ={recipe.cmp_focus_sigma_nm:.1f} nm)`",
        f"- **포토 레시피**: `BARC={recipe.barc_thickness_nm:.1f} nm` | `PR={pr_thickness_nm:.1f} nm ({recipe.spin_speed_rpm:.0f} RPM)` | `Dose={recipe.exposure_dose_mj_cm2:.2f} mJ/cm²` | `Focus Offset={recipe.focus_offset_nm:+.1f} nm` | `PEB={recipe.peb_temp_c:.1f}°C (±{recipe.peb_radial_range_c:.1f}°C)`",
        "",
        "### 1. 공정 결과 성적표 (ADI 계측 · 광학 · Etch ACI 연계)",
        "| 지표 구분 | 측정 / 계산 결과 | 목표 기준 | 판정 |",
        "| :--- | :---: | :---: | :---: |",
        f"| **최종 ACI 평균 CD** | **{aci_mean:.2f} nm** | {recipe.target_aci_cd_nm:.1f} ± {recipe.target_aci_cd_nm*0.1:.1f} nm | {'✅ 양호' if abs(aci_mean - recipe.target_aci_cd_nm) <= recipe.target_aci_cd_nm*0.03 else '⚠️ 보정 필요'} |",
        f"| **포토 ADI 평균 CD** (Etch Bias {recipe.etch_bias_nm:+.1f}nm 반영) | {cdu.mean_cd_nm:.2f} nm | {target_adi_cd_nm:.1f} nm | {'✅ 양호' if abs(cdu.mean_cd_nm - target_adi_cd_nm) <= 1.2 else '⚠️ 이탈'} |",
        f"| **웨이퍼 CDU (3σ)** | **{aci_3s:.2f} nm** ({100*aci_3s/max(recipe.target_aci_cd_nm,1e-6):.2f}%) | ≤ 3.0% ({recipe.target_aci_cd_nm*0.03:.2f} nm) | {'✅ 우수' if 100*aci_3s/max(recipe.target_aci_cd_nm,1e-6) <= 3.5 else '❌ 과다'} |",
        f"| **하부 반사율 R_sub / SWR** | {optics.substrate_reflectance*100:.2f}% / {optics.swr_local:.2f} | R_sub < 2.0%, SWR < 2.0 | {'✅ 억제됨' if optics.substrate_reflectance <= 0.03 else '❌ 반사 과다'} |",
        f"| **유효 흡수 광량 계수 η_abs** | {optics.effective_dose_factor:.3f} (총 반사 손실 {optics.reflectance*100:.1f}%) | 안정적 Swing 억제 | ℹ️ 참조 |",
        f"| **Process Window (DOF @ EL%)** | {pw.pw_dof_nm:.1f} nm @ {pw.pw_el_pct:.2f}% (Area {pw.pw_area:.0f}) | DOF ≥ 100nm, EL ≥ 5% | {'✅ 넉넉함' if pw.pw_dof_nm >= 100 and pw.pw_el_pct >= 5 else '⚠️ 마진 부족'} |",
        f"| **결함 위험도 (동작점 기준)** | **{defects.overall_defect_risk:.1f} / 100** ({', '.join(defects.flags) if defects.flags else '결함 플래그 없음'}) | < 25 / 100 | {'✅ 안전' if defects.overall_defect_risk < 25 else '❌ 위험'} |",
        f"| **후속 Etch용 PR 두께 마진** | {etch_pr_margin:+.1f} nm (AR={defects.aspect_ratio:.2f}) | PR ≥ {recipe.min_pr_for_etch_nm:.0f}nm, AR ≤ 3.0 | {'✅ 적합' if etch_pr_margin >= 0 and defects.aspect_ratio <= 2.8 else '⚠️ 주의'} |",
        "",
        "### 2. 데이터 분석 (불량 원인 분해 & 통계 진단)",
        "#### 2-1. CD 오차·산포 물리 원인 분해 (Root-Cause Variance Attribution)",
        "| 순위 | 공정 원인 인자 | 단독 RMS 오차 (nm) | 불량 분산 기여율 (%) | 진단 내용 |",
        "| :---: | :--- | :---: | :---: | :--- |",
    ]
    for rank, row in enumerate(breakdown, start=1):
        lines.append(
            f"| {rank} | **{row['cause']}** | {row['rms_error_nm']:.2f} nm | {row['variance_share_pct']:.1f}% | {row['description']} |"
        )

    lines.extend([
        "",
        "#### 2-2. 웨이퍼 면내 277개 사이트 다중회귀(OLS) 민감도 Top 3",
    ])
    for d in ols_drivers[:3]:
        lines.append(
            f"- `{d['feature']}`: 표준화 회귀계수 `std_beta = {d['std_beta']:+.3f}` (p-value = {d['p_value']:.2e})"
        )

    lines.extend([
        "",
        "### 3. 향후 필요한 조치사항 (CAPA — 다음 차수 시뮬레이션 개선 계획)",
    ])
    if not actions:
        lines.append("- ✅ **모든 핵심 지표(수율 ≥ 95%, 반사율 < 2%, 결함 위험 없음)가 목표 기준을 충족했습니다.** 현재 레시피를 양산 기준(POR)으로 확정 가능합니다.")
    else:
        for idx, act in enumerate(actions, start=1):
            lines.append(
                f"{idx}. **[{act.priority}] {act.stage}**\n"
                f"   - **현재 문제**: {act.issue}\n"
                f"   - **권장 조치**: {act.action}\n"
                f"   - **기대 효과**: {act.expected_effect}"
            )
    return "\n".join(lines)


def run_fab_cycle(
    recipe: FabRecipe,
    cycle_id: int = 1,
    seed: int = 42,
    label: Optional[str] = None,
) -> CycleResult:
    """Execute one complete end-to-end Fab photolithography simulation cycle and generate its report."""
    node = EXPOSURE_NODES[recipe.node_key]
    if node.comparison_only:
        raise ValueError(f"Node '{recipe.node_key}' is comparison-only and cannot run DUV Fab cycle")

    # 1. Track Spin Coating -> PR thickness
    pr_thick = spin_coating_thickness_nm(
        spin_speed_rpm=recipe.spin_speed_rpm,
        viscosity_cp=recipe.pr_viscosity_cp,
    )

    # 2. Downstream Etch Bias -> Photo ADI target CD
    target_adi_cd = max(10.0, recipe.target_aci_cd_nm - recipe.etch_bias_nm)

    # 3. Optical TMM stack + optimal BARC reference
    ambient = get_ambient_for_node(recipe.node_key)
    stack = build_litho_stack(
        wavelength_nm=node.wavelength_nm,
        ambient_material=ambient,
        pr_thickness_nm=pr_thick,
        barc_thickness_nm=recipe.barc_thickness_nm,
        underlayer_material=recipe.underlayer_material,
        underlayer_thickness_nm=recipe.underlayer_thickness_nm,
    )
    optics = simulate_multilayer_optics(stack, node.wavelength_nm, n_z_points=100)
    barc_opt = optimize_barc_thickness(
        wavelength_nm=node.wavelength_nm,
        ambient_material=ambient,
        pr_thickness_nm=pr_thick,
        underlayer_material=recipe.underlayer_material,
        underlayer_thickness_nm=recipe.underlayer_thickness_nm,
    )
    opt_barc_nm = float(barc_opt["optimal_barc_nm"])
    min_barc_refl = float(barc_opt["min_substrate_reflectance"])

    # 4. Optical resolution & DOF
    min_cd = float(rayleigh_resolution(node.wavelength_nm, recipe.na, k1=node.k1_default, illumination=recipe.illumination))
    dof_hi = float(
        depth_of_focus(
            node.wavelength_nm,
            recipe.na,
            k2=node.k2_default,
            n_fluid=node.n_fluid,
            illumination=recipe.illumination,
            pattern=recipe.pattern,
            high_na=True,
        )
    )

    # 5. Tier 2 bake & develop shift + Optics-Coupled FEM
    t2_nom = tier2_process_shift(
        soft_bake_temp_c=recipe.soft_bake_temp_c,
        peb_temp_c=recipe.peb_temp_c,
        hard_bake_temp_c=recipe.hard_bake_temp_c,
        dev_time_s=recipe.dev_time_s,
        dev_conc_wt_pct=recipe.dev_conc_wt_pct,
        target_cd_nm=target_adi_cd,
    )
    fem = simulate_fem(
        node_key=recipe.node_key,
        na=recipe.na,
        illumination=recipe.illumination,
        pattern=recipe.pattern,
        pr_thickness_nm=pr_thick,
        barc_thickness_nm=recipe.barc_thickness_nm,
        underlayer_material=recipe.underlayer_material,
        underlayer_thickness_nm=recipe.underlayer_thickness_nm,
        target_cd_nm=target_adi_cd,
        n_dose=31,
        n_focus=37,
        best_focus_nm=-recipe.cmp_dishing_defocus_nm,
        process_cd_bias_nm=t2_nom["process_cd_bias_nm"],
        contrast_modifier=t2_nom["contrast_modifier"],
        hmds_score=recipe.hmds_score,
        soft_bake_temp_c=recipe.soft_bake_temp_c,
    )

    # 6. 300mm Wafer full simulation + Etch ACI mapping
    cdu_res, focus_site, dose_site, eta_site, _, _ = _compute_wafer_sites(
        recipe=recipe,
        pr_thickness_nm=pr_thick,
        target_adi_cd_nm=target_adi_cd,
        dof_scale_nm=dof_hi,
        t2_nominal=t2_nom,
        seed=seed + cycle_id * 17,
    )
    aci_sites = np.maximum(0.0, cdu_res.cd_nm + recipe.etch_bias_nm)
    aci_mean = float(np.mean(aci_sites))
    aci_std = float(np.std(aci_sites, ddof=1))
    aci_3s = 3.0 * aci_std
    aci_3s_pct = 100.0 * aci_3s / max(recipe.target_aci_cd_nm, 1e-6)
    tol_aci = recipe.target_aci_cd_nm * DEFECT_THRESHOLDS["cd_spec_tolerance_ratio"]
    aci_yield = float(100.0 * np.mean(np.abs(aci_sites - recipe.target_aci_cd_nm) <= tol_aci))
    etch_pr_margin = pr_thick - recipe.min_pr_for_etch_nm

    # 7. Evaluate defects at actual operating point
    mean_eff_focus = recipe.focus_offset_nm + recipe.cmp_dishing_defocus_nm
    c_op = float(
        aerial_image_contrast(
            mean_eff_focus,
            wavelength_nm=node.wavelength_nm,
            na=recipe.na,
            n_fluid=node.n_fluid,
            target_cd_nm=target_adi_cd,
            illumination=recipe.illumination,
            pattern=recipe.pattern,
            k1_base=node.k1_default,
            k2_base=node.k2_default,
            best_focus_nm=0.0,
        )
    )
    defects_op = evaluate_defects(
        cd_nm=cdu_res.mean_cd_nm,
        target_cd_nm=target_adi_cd,
        pr_thickness_nm=pr_thick,
        effective_dose_mj_cm2=recipe.exposure_dose_mj_cm2 * optics.effective_dose_factor,
        nominal_dose_mj_cm2=node.nominal_dose_mj_cm2,
        aerial_contrast=c_op,
        substrate_reflectance=optics.substrate_reflectance,
        swr_local=optics.swr_local,
        hmds_score=recipe.hmds_score,
        soft_bake_temp_c=recipe.soft_bake_temp_c,
    )

    # 8. Root-cause decomposition & CAPA actions
    breakdown, ols_drivers = _decompose_error_sources(
        recipe=recipe,
        pr_thickness_nm=pr_thick,
        target_adi_cd_nm=target_adi_cd,
        dof_scale_nm=dof_hi,
        optics_center=optics,
        cdu_res=cdu_res,
        focus_site=focus_site,
        dose_site=dose_site,
        eta_site=eta_site,
    )
    actions, step_recipe, full_recipe = _diagnose_actions(
        recipe=recipe,
        pr_thickness_nm=pr_thick,
        target_adi_cd_nm=target_adi_cd,
        dof_scale_nm=dof_hi,
        optics=optics,
        optimal_barc_nm=opt_barc_nm,
        min_barc_refl=min_barc_refl,
        defects=defects_op,
        cdu_res=cdu_res,
        aci_yield_pct=aci_yield,
        t2_nom=t2_nom,
    )

    cycle_label = label or (
        "초기 불량 Baseline" if cycle_id == 1 else f"개선 적용 {cycle_id}차"
    )
    report_md = _build_cycle_report_markdown(
        cycle_id=cycle_id,
        label=cycle_label,
        recipe=recipe,
        pr_thickness_nm=pr_thick,
        target_adi_cd_nm=target_adi_cd,
        optics=optics,
        optimal_barc_nm=opt_barc_nm,
        fem=fem,
        defects=defects_op,
        cdu=cdu_res,
        aci_mean=aci_mean,
        aci_3s=aci_3s,
        aci_yield=aci_yield,
        etch_pr_margin=etch_pr_margin,
        breakdown=breakdown,
        ols_drivers=ols_drivers,
        actions=actions,
    )

    return CycleResult(
        cycle_id=cycle_id,
        label=cycle_label,
        recipe=recipe,
        pr_thickness_nm=pr_thick,
        target_adi_cd_nm=target_adi_cd,
        target_aci_cd_nm=recipe.target_aci_cd_nm,
        min_cd_nm=min_cd,
        dof_high_na_nm=dof_hi,
        optics=optics,
        optimal_barc_nm=opt_barc_nm,
        min_barc_reflectance=min_barc_refl,
        fem=fem,
        defects_operating=defects_op,
        wafer_cdu=cdu_res,
        aci_cd_sites_nm=aci_sites,
        aci_mean_cd_nm=aci_mean,
        aci_cdu_3sigma_nm=aci_3s,
        aci_cdu_3sigma_pct=aci_3s_pct,
        adi_yield_pct=cdu_res.within_spec_yield_pct,
        aci_yield_pct=aci_yield,
        cd_bias_error_nm=cdu_res.mean_cd_nm - target_adi_cd,
        etch_pr_margin_nm=etch_pr_margin,
        variance_breakdown=breakdown,
        ols_top_drivers=ols_drivers,
        action_items=actions,
        recommended_stepwise_recipe=step_recipe,
        recommended_full_recipe=full_recipe,
        report_markdown=report_md,
    )


def build_cumulative_summary_markdown(history: Sequence[CycleResult]) -> str:
    """Compile a multi-cycle cumulative Run-to-Run yield improvement report."""
    if not history:
        return "아직 실행된 시뮬레이션 사이클이 없습니다."

    first = history[0]
    last = history[-1]
    yield_gain = last.aci_yield_pct - first.aci_yield_pct

    lines = [
        "# 🏭 포토공정 Run-to-Run 반복 수율 개선 종합 보고서",
        "",
        f"- **총 실행 사이클**: {len(history)}회 (`1차` → `{last.cycle_id}차`)",
        f"- **최종 ACI 수율 변화**: **{first.aci_yield_pct:.1f}% → {last.aci_yield_pct:.1f}%** ({yield_gain:+.1f}%p)",
        f"- **웨이퍼 CDU (3σ) 변화**: **{first.aci_cdu_3sigma_nm:.2f} nm → {last.aci_cdu_3sigma_nm:.2f} nm**",
        "",
        "## 회차별 누적 성적 비교표",
        "| 차수 | 설명 | ACI 수율 (%) | ADI 수율 (%) | ACI 평균 CD (nm) | CDU 3σ (nm) | R_sub (%) | 결함 위험도 |",
        "| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for c in history:
        lines.append(
            f"| {c.cycle_id}차 | {c.label} | **{c.aci_yield_pct:.1f}%** | {c.adi_yield_pct:.1f}% | "
            f"{c.aci_mean_cd_nm:.2f} | {c.aci_cdu_3sigma_nm:.2f} | {c.optics.substrate_reflectance*100:.2f}% | {c.defects_operating.overall_defect_risk:.1f} |"
        )
    lines.append("")
    for c in history:
        lines.append("---")
        lines.append(c.report_markdown)
    return "\n".join(lines)
