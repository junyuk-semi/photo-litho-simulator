"""Stage 4: Optics-Coupled Focus-Exposure Matrix (FEM), Bossung Model, Process Window & Defects.

Couples Stage 3 TMM optical output (effective_dose_factor eta_abs, reflectance, SWR)
directly into the Bossung FEM exposure axis (E_eff = Dose * eta_abs) and defect rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

from .constants import (
    DEFECT_THRESHOLDS,
    EXPOSURE_NODES,
    ILLUMINATION_PRESETS,
    PATTERN_PRESETS,
)
from .optics_tmm import (
    OpticalStackResult,
    build_litho_stack,
    get_ambient_for_node,
    simulate_multilayer_optics,
)
from .resolution import depth_of_focus, effective_k1


@dataclass(frozen=True)
class DefectAssessment:
    """Quantitative defect risk indicators (0..100 score + binary risk flags)."""

    aspect_ratio: float
    pattern_collapse_risk: float
    scumming_risk: float
    bridging_pinching_risk: float
    notching_risk: float
    overall_defect_risk: float
    flags: Tuple[str, ...]


@dataclass(frozen=True)
class ProcessWindowResult:
    """Process Window extracted from +/- 10% CD corridor in Focus-Exposure space."""

    target_cd_nm: float
    cd_tolerance_nm: float
    best_dose_mj_cm2: float
    best_focus_nm: float
    max_dof_nm: float
    max_el_pct: float
    pw_dof_nm: float  # DOF of max-area inscribed rectangle
    pw_el_pct: float  # Exposure Latitude (%) of max-area inscribed rectangle
    pw_area: float  # pw_dof_nm * pw_el_pct
    pw_dose_bounds: Tuple[float, float]
    pw_focus_bounds: Tuple[float, float]
    in_spec_fraction: float


@dataclass(frozen=True)
class FEMResult:
    """Full Focus-Exposure Matrix simulation output."""

    node_key: str
    pattern: str
    illumination: str
    underlayer: str
    barc_thickness_nm: float
    target_cd_nm: float
    dose_grid_mj_cm2: np.ndarray  # shape (n_dose,)
    focus_grid_nm: np.ndarray  # shape (n_focus,)
    cd_matrix_nm: np.ndarray  # shape (n_dose, n_focus)
    contrast_grid: np.ndarray  # shape (n_focus,)
    in_spec_mask: np.ndarray  # shape (n_dose, n_focus) bool
    optics: OpticalStackResult
    process_window: ProcessWindowResult
    defects_at_center: DefectAssessment


def aerial_image_contrast(
    focus_nm: np.ndarray | float,
    wavelength_nm: float,
    na: float,
    n_fluid: float,
    target_cd_nm: float,
    illumination: str = "Annular",
    pattern: str = "Dense_1to1",
    k1_base: float = 0.32,
    k2_base: float = 0.50,
    best_focus_nm: float = 0.0,
) -> np.ndarray | float:
    """Compute approximate Aerial Image Contrast C(dz) in [0, 1] accounting for k1 and DOF."""
    dz = np.asarray(focus_nm, dtype=float) - best_focus_nm
    k1_eff = effective_k1(k1_base, illumination=illumination, clamp_physical_limit=True)
    cd_min = k1_eff * wavelength_nm / na
    # Baseline contrast increases when target CD exceeds Rayleigh resolution limit
    res_ratio = target_cd_nm / max(cd_min, 1e-6)
    c0 = float(np.clip(0.35 + 0.55 * (1.0 - np.exp(-1.2 * max(res_ratio - 0.65, 0.0))), 0.15, 0.92))

    dof_scale = float(
        depth_of_focus(
            wavelength_nm,
            na,
            k2=k2_base,
            n_fluid=n_fluid,
            illumination=illumination,
            pattern=pattern,
            high_na=True,
        )
    )
    w_dof = max(dof_scale * 1.15, 20.0)
    contrast = c0 * np.exp(-0.5 * (dz / w_dof) ** 2)
    return float(contrast) if np.ndim(contrast) == 0 else contrast


def bossung_cd(
    dose_mj_cm2: np.ndarray | float,
    focus_nm: np.ndarray | float,
    target_cd_nm: float,
    nominal_dose_mj_cm2: float,
    dof_scale_nm: float,
    effective_dose_factor: float = 1.0,
    pattern: str = "Dense_1to1",
    illumination: str = "Annular",
    best_focus_nm: float = 0.0,
    process_cd_bias_nm: float = 0.0,
    contrast_modifier: float = 1.0,
) -> np.ndarray | float:
    """Compute Positive-PR Line CD(Dose, Focus) via Optics-Coupled Bossung model.

    Physical invariants:
    - Positive PR: Dose increase -> Line CD monotonically decreases.
    - Best Focus (dz = z0): dCD/dz = 0.
    - Iso-focal transition: curvature flips sign around E_iso (Smile vs Frown).
    - Optics coupling: E_eff = Dose * eta_abs shifts the effective Dose axis.
    """
    dose = np.asarray(dose_mj_cm2, dtype=float)
    dz = np.asarray(focus_nm, dtype=float) - best_focus_nm
    if np.any(dose <= 0):
        raise ValueError("Exposure dose must be strictly positive")
    if effective_dose_factor <= 0:
        raise ValueError("effective_dose_factor must be strictly positive")

    pat = PATTERN_PRESETS[pattern]
    illum = ILLUMINATION_PRESETS[illumination]

    e_eff = dose * effective_dose_factor
    e_iso = nominal_dose_mj_cm2 * pat.iso_focal_dose_ratio

    # Dose sensitivity S_E (nm per unit log-dose); better OAI/contrast lowers sensitivity slightly
    s_e = (0.58 * target_cd_nm) / max(contrast_modifier * (1.05 / illum.k1_factor) ** 0.25, 0.5)

    # Normalized defocus squared (dimensionless)
    u = dz / max(dof_scale_nm, 20.0)

    # Curvature coefficients scaled to target_cd_nm so Dense/Iso smile-frown is physically realistic
    kappa_0 = pat.bossung_base_curvature * 0.14 * target_cd_nm
    # Keep |kappa_E * u^2| bounded below s_e so Positive-PR dose monotonicity holds across FEM
    kappa_e = -0.18 * target_cd_nm
    log_e_nom = np.log(e_eff / nominal_dose_mj_cm2)
    log_e_iso = np.log(e_eff / e_iso)

    cd = target_cd_nm - s_e * log_e_nom + (kappa_0 + kappa_e * log_e_iso) * (u**2) + process_cd_bias_nm
    cd = np.maximum(cd, 0.0)
    return float(cd) if np.ndim(cd) == 0 else cd


def evaluate_defects(
    cd_nm: float,
    target_cd_nm: float,
    pr_thickness_nm: float,
    effective_dose_mj_cm2: float,
    nominal_dose_mj_cm2: float,
    aerial_contrast: float,
    substrate_reflectance: float,
    swr_local: float,
    hmds_score: float = 1.0,
    soft_bake_temp_c: float = 105.0,
) -> DefectAssessment:
    """Compute quantitative defect risk scores (0..100) and triggered flags."""
    ar = pr_thickness_nm / max(cd_nm, 1.0)
    ar_limit = (
        DEFECT_THRESHOLDS["aspect_ratio_collapse_no_hmds"]
        + hmds_score
        * (
            DEFECT_THRESHOLDS["aspect_ratio_collapse_hmds"]
            - DEFECT_THRESHOLDS["aspect_ratio_collapse_no_hmds"]
        )
    )
    collapse_risk = float(np.clip(100.0 * (ar - 0.65 * ar_limit) / (0.65 * ar_limit), 0.0, 100.0))

    dose_ratio = effective_dose_mj_cm2 / max(nominal_dose_mj_cm2, 1e-6)
    cd_ratio = cd_nm / max(target_cd_nm, 1e-6)
    sb_penalty = max(0.0, (soft_bake_temp_c - 115.0) * 3.0)
    scum_base = max(
        0.0,
        (DEFECT_THRESHOLDS["scumming_dose_ratio_min"] - dose_ratio) * 260.0,
        (cd_ratio - 1.10) * 320.0,
    )
    scumming_risk = float(np.clip(scum_base + sb_penalty, 0.0, 100.0))

    bridge_base = max(
        0.0,
        (0.85 - cd_ratio) * 350.0,
        (DEFECT_THRESHOLDS["min_aerial_contrast"] - aerial_contrast) * 320.0,
    )
    bridging_risk = float(np.clip(bridge_base, 0.0, 100.0))

    r_score = 100.0 * max(0.0, substrate_reflectance - 0.03) / 0.25
    swr_score = 100.0 * max(0.0, swr_local - 1.15) / 1.50
    notching_risk = float(np.clip(max(r_score, swr_score), 0.0, 100.0))

    flags = []
    if ar > ar_limit:
        flags.append("Pattern Collapse")
    if dose_ratio < DEFECT_THRESHOLDS["scumming_dose_ratio_min"] or cd_ratio > DEFECT_THRESHOLDS["scumming_cd_ratio_max"] or soft_bake_temp_c > 125.0:
        flags.append("Scumming")
    if cd_ratio < DEFECT_THRESHOLDS["bridging_cd_ratio_min"] or aerial_contrast < DEFECT_THRESHOLDS["min_aerial_contrast"]:
        flags.append("Bridging/Pinching")
    if substrate_reflectance > DEFECT_THRESHOLDS["notching_reflectance_max"] or swr_local > DEFECT_THRESHOLDS["notching_swr_max"]:
        flags.append("Reflective Notching")

    overall = float(np.clip(max(collapse_risk, scumming_risk, bridging_risk, notching_risk), 0.0, 100.0))
    return DefectAssessment(
        aspect_ratio=float(ar),
        pattern_collapse_risk=collapse_risk,
        scumming_risk=scumming_risk,
        bridging_pinching_risk=bridging_risk,
        notching_risk=notching_risk,
        overall_defect_risk=overall,
        flags=tuple(flags),
    )


def extract_process_window(
    dose_grid_mj_cm2: np.ndarray,
    focus_grid_nm: np.ndarray,
    cd_matrix_nm: np.ndarray,
    target_cd_nm: float,
    tolerance_ratio: float = 0.10,
) -> ProcessWindowResult:
    """Find max-area inscribed rectangle inside +/- tolerance_ratio CD corridor."""
    tol_nm = target_cd_nm * tolerance_ratio
    in_spec = np.abs(cd_matrix_nm - target_cd_nm) <= tol_nm
    n_dose, n_focus = in_spec.shape

    if not np.any(in_spec):
        mid_d = float(dose_grid_mj_cm2[n_dose // 2])
        mid_f = float(focus_grid_nm[n_focus // 2])
        return ProcessWindowResult(
            target_cd_nm=target_cd_nm,
            cd_tolerance_nm=tol_nm,
            best_dose_mj_cm2=mid_d,
            best_focus_nm=mid_f,
            max_dof_nm=0.0,
            max_el_pct=0.0,
            pw_dof_nm=0.0,
            pw_el_pct=0.0,
            pw_area=0.0,
            pw_dose_bounds=(mid_d, mid_d),
            pw_focus_bounds=(mid_f, mid_f),
            in_spec_fraction=0.0,
        )

    # Max 1D DOF across rows & max 1D EL% across columns
    max_dof = 0.0
    for r in range(n_dose):
        idx = np.where(in_spec[r])[0]
        if idx.size >= 2:
            # Longest contiguous run
            splits = np.where(np.diff(idx) > 1)[0] + 1
            for run in np.split(idx, splits):
                span = float(focus_grid_nm[run[-1]] - focus_grid_nm[run[0]])
                if span > max_dof:
                    max_dof = span

    max_el = 0.0
    for c in range(n_focus):
        idx = np.where(in_spec[:, c])[0]
        if idx.size >= 2:
            splits = np.where(np.diff(idx) > 1)[0] + 1
            for run in np.split(idx, splits):
                d_lo, d_hi = float(dose_grid_mj_cm2[run[0]]), float(dose_grid_mj_cm2[run[-1]])
                d_mid = 0.5 * (d_lo + d_hi)
                el = 100.0 * (d_hi - d_lo) / max(d_mid, 1e-6)
                if el > max_el:
                    max_el = el

    # Max-area inscribed rectangle in physical (EL% * DOF_nm) units
    best_area = -1.0
    best_rect = (0, 0, 0, 0)  # r1, r2, c1, c2
    best_dof = 0.0
    best_el = 0.0

    for r1 in range(n_dose):
        row_mask = in_spec[r1].copy()
        for r2 in range(r1, n_dose):
            row_mask &= in_spec[r2]
            if not np.any(row_mask):
                break
            idx = np.where(row_mask)[0]
            if idx.size < 2:
                continue
            d_lo = float(dose_grid_mj_cm2[r1])
            d_hi = float(dose_grid_mj_cm2[r2])
            d_mid = 0.5 * (d_lo + d_hi)
            el_pct = 100.0 * (d_hi - d_lo) / max(d_mid, 1e-6)
            if el_pct <= 0.0:
                continue
            splits = np.where(np.diff(idx) > 1)[0] + 1
            for run in np.split(idx, splits):
                if run.size < 2:
                    continue
                c1, c2 = int(run[0]), int(run[-1])
                dof_nm = float(focus_grid_nm[c2] - focus_grid_nm[c1])
                area = el_pct * dof_nm
                if area > best_area:
                    best_area = area
                    best_rect = (r1, r2, c1, c2)
                    best_dof = dof_nm
                    best_el = el_pct

    if best_area <= 0.0:
        r_idx, c_idx = np.where(in_spec)
        best_dose = float(np.mean(dose_grid_mj_cm2[r_idx]))
        best_focus = float(np.mean(focus_grid_nm[c_idx]))
        return ProcessWindowResult(
            target_cd_nm=target_cd_nm,
            cd_tolerance_nm=tol_nm,
            best_dose_mj_cm2=best_dose,
            best_focus_nm=best_focus,
            max_dof_nm=max_dof,
            max_el_pct=max_el,
            pw_dof_nm=0.0,
            pw_el_pct=0.0,
            pw_area=0.0,
            pw_dose_bounds=(best_dose, best_dose),
            pw_focus_bounds=(best_focus, best_focus),
            in_spec_fraction=float(np.mean(in_spec)),
        )

    r1, r2, c1, c2 = best_rect
    d_bounds = (float(dose_grid_mj_cm2[r1]), float(dose_grid_mj_cm2[r2]))
    f_bounds = (float(focus_grid_nm[c1]), float(focus_grid_nm[c2]))
    return ProcessWindowResult(
        target_cd_nm=target_cd_nm,
        cd_tolerance_nm=tol_nm,
        best_dose_mj_cm2=0.5 * (d_bounds[0] + d_bounds[1]),
        best_focus_nm=0.5 * (f_bounds[0] + f_bounds[1]),
        max_dof_nm=max_dof,
        max_el_pct=max_el,
        pw_dof_nm=best_dof,
        pw_el_pct=best_el,
        pw_area=float(best_area),
        pw_dose_bounds=d_bounds,
        pw_focus_bounds=f_bounds,
        in_spec_fraction=float(np.mean(in_spec)),
    )


def simulate_fem(
    node_key: str = "ArFi_193",
    na: Optional[float] = None,
    illumination: str = "Annular",
    pattern: str = "Dense_1to1",
    pr_thickness_nm: Optional[float] = None,
    barc_thickness_nm: float = 40.0,
    underlayer_material: str = "Bare_Si",
    underlayer_thickness_nm: float = 100.0,
    target_cd_nm: Optional[float] = None,
    dose_range_mj_cm2: Optional[Tuple[float, float]] = None,
    focus_range_nm: Tuple[float, float] = (-180.0, 180.0),
    n_dose: int = 41,
    n_focus: int = 49,
    best_focus_nm: float = 0.0,
    process_cd_bias_nm: float = 0.0,
    contrast_modifier: float = 1.0,
    hmds_score: float = 1.0,
    soft_bake_temp_c: float = 105.0,
) -> FEMResult:
    """Run full Optics-Coupled Focus-Exposure Matrix simulation."""
    node = EXPOSURE_NODES[node_key]
    if node.comparison_only:
        raise ValueError(f"Node '{node_key}' is comparison-only (Stage 2) and not supported for DUV TMM/FEM")

    na_val = node.na_default if na is None else float(na)
    d_pr = node.default_pr_thickness_nm if pr_thickness_nm is None else float(pr_thickness_nm)
    t_cd = node.default_target_cd_nm if target_cd_nm is None else float(target_cd_nm)

    if dose_range_mj_cm2 is None:
        e_nom = node.nominal_dose_mj_cm2
        dose_range_mj_cm2 = (0.65 * e_nom, 1.35 * e_nom)

    ambient = get_ambient_for_node(node_key)
    stack = build_litho_stack(
        wavelength_nm=node.wavelength_nm,
        ambient_material=ambient,
        pr_thickness_nm=d_pr,
        barc_thickness_nm=barc_thickness_nm,
        underlayer_material=underlayer_material,
        underlayer_thickness_nm=underlayer_thickness_nm,
    )
    optics = simulate_multilayer_optics(stack, wavelength_nm=node.wavelength_nm, n_z_points=120)

    dof_scale = float(
        depth_of_focus(
            node.wavelength_nm,
            na_val,
            k2=node.k2_default,
            n_fluid=node.n_fluid,
            illumination=illumination,
            pattern=pattern,
            high_na=True,
        )
    )

    dose_grid = np.linspace(dose_range_mj_cm2[0], dose_range_mj_cm2[1], n_dose)
    focus_grid = np.linspace(focus_range_nm[0], focus_range_nm[1], n_focus)
    dose_mesh, focus_mesh = np.meshgrid(dose_grid, focus_grid, indexing="ij")

    cd_matrix = np.asarray(
        bossung_cd(
            dose_mesh,
            focus_mesh,
            target_cd_nm=t_cd,
            nominal_dose_mj_cm2=node.nominal_dose_mj_cm2,
            dof_scale_nm=dof_scale,
            effective_dose_factor=optics.effective_dose_factor,
            pattern=pattern,
            illumination=illumination,
            best_focus_nm=best_focus_nm,
            process_cd_bias_nm=process_cd_bias_nm,
            contrast_modifier=contrast_modifier,
        ),
        dtype=float,
    )

    contrast_grid = np.asarray(
        aerial_image_contrast(
            focus_grid,
            wavelength_nm=node.wavelength_nm,
            na=na_val,
            n_fluid=node.n_fluid,
            target_cd_nm=t_cd,
            illumination=illumination,
            pattern=pattern,
            k1_base=node.k1_default,
            k2_base=node.k2_default,
            best_focus_nm=best_focus_nm,
        ),
        dtype=float,
    )

    pw = extract_process_window(
        dose_grid,
        focus_grid,
        cd_matrix,
        target_cd_nm=t_cd,
        tolerance_ratio=DEFECT_THRESHOLDS["cd_spec_tolerance_ratio"],
    )
    in_spec = np.abs(cd_matrix - t_cd) <= pw.cd_tolerance_nm

    # Evaluate defects at Process Window center
    cd_center = float(
        bossung_cd(
            pw.best_dose_mj_cm2,
            pw.best_focus_nm,
            target_cd_nm=t_cd,
            nominal_dose_mj_cm2=node.nominal_dose_mj_cm2,
            dof_scale_nm=dof_scale,
            effective_dose_factor=optics.effective_dose_factor,
            pattern=pattern,
            illumination=illumination,
            best_focus_nm=best_focus_nm,
            process_cd_bias_nm=process_cd_bias_nm,
            contrast_modifier=contrast_modifier,
        )
    )
    c_center = float(
        aerial_image_contrast(
            pw.best_focus_nm,
            wavelength_nm=node.wavelength_nm,
            na=na_val,
            n_fluid=node.n_fluid,
            target_cd_nm=t_cd,
            illumination=illumination,
            pattern=pattern,
            k1_base=node.k1_default,
            k2_base=node.k2_default,
            best_focus_nm=best_focus_nm,
        )
    )
    defects = evaluate_defects(
        cd_nm=cd_center,
        target_cd_nm=t_cd,
        pr_thickness_nm=d_pr,
        effective_dose_mj_cm2=pw.best_dose_mj_cm2 * optics.effective_dose_factor,
        nominal_dose_mj_cm2=node.nominal_dose_mj_cm2,
        aerial_contrast=c_center,
        substrate_reflectance=optics.substrate_reflectance,
        swr_local=optics.swr_local,
        hmds_score=hmds_score,
        soft_bake_temp_c=soft_bake_temp_c,
    )

    return FEMResult(
        node_key=node_key,
        pattern=pattern,
        illumination=illumination,
        underlayer=underlayer_material,
        barc_thickness_nm=barc_thickness_nm,
        target_cd_nm=t_cd,
        dose_grid_mj_cm2=dose_grid,
        focus_grid_nm=focus_grid,
        cd_matrix_nm=cd_matrix,
        contrast_grid=contrast_grid,
        in_spec_mask=in_spec,
        optics=optics,
        process_window=pw,
        defects_at_center=defects,
    )
