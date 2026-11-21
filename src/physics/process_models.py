"""Stage 5 (Tier 2): Spin coating, Arrhenius PEB diffusion, Mack dissolution & 300mm Wafer CDU Map."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

from .constants import DEFECT_THRESHOLDS, EXPOSURE_NODES
from .exposure_fem import bossung_cd
from .optics_tmm import build_litho_stack, get_ambient_for_node, simulate_multilayer_optics
from .resolution import depth_of_focus

KB_EV_PER_K = 8.617333262e-5


@dataclass(frozen=True)
class WaferCDUResult:
    """300mm wafer spatial CD uniformity simulation result."""

    node_key: str
    target_cd_nm: float
    x_mm: np.ndarray
    y_mm: np.ndarray
    radius_mm: np.ndarray
    pr_thickness_nm: np.ndarray
    peb_temp_c: np.ndarray
    cd_nm: np.ndarray
    mean_cd_nm: float
    std_cd_nm: float
    cdu_3sigma_nm: float
    cdu_3sigma_pct: float
    within_spec_yield_pct: float


def spin_coating_thickness_nm(
    spin_speed_rpm: float = 3000.0,
    viscosity_cp: float = 3.0,
    pr_temp_c: float = 22.0,
    spin_time_s: float = 45.0,
    k_spin: float = 4558.0,
) -> float:
    """Meyerhofer spin-coating scaling: d_PR ~ K * eta(T)^(1/3) * omega^(-1/2) * f(t_spin).

    Calibrated so (3000 RPM, 3.0 cP, 22 C, 45 s) yields ~120 nm (ArFi baseline).
    """
    if spin_speed_rpm <= 0 or viscosity_cp <= 0 or spin_time_s <= 0:
        raise ValueError("spin_speed_rpm, viscosity_cp, and spin_time_s must be positive")
    eta_eff = viscosity_cp * np.exp(-0.025 * (pr_temp_c - 22.0))
    # Short spin time leaves slightly thicker wet film; saturates after ~30 s
    time_factor = 1.0 + 0.12 * np.exp(-spin_time_s / 15.0)
    time_ref = 1.0 + 0.12 * np.exp(-45.0 / 15.0)
    thickness = k_spin * (eta_eff ** (1.0 / 3.0)) * (spin_speed_rpm ** -0.5) * (time_factor / time_ref)
    return float(thickness)


def peb_diffusion_length_nm(
    peb_temp_c: float = 115.0,
    peb_time_s: float = 60.0,
    ea_ev: float = 0.85,
    d0_nm2_per_s: float = 2.0e11,
) -> float:
    """Arrhenius CAR acid diffusion length L_diff = sqrt(2 * D(T) * t_PEB) in nm."""
    if peb_time_s <= 0:
        raise ValueError("peb_time_s must be positive")
    t_kelvin = peb_temp_c + 273.15
    diffusivity = d0_nm2_per_s * np.exp(-ea_ev / (KB_EV_PER_K * t_kelvin))
    return float(np.sqrt(2.0 * diffusivity * peb_time_s))


def mack_dissolution_rate(
    m_pac: np.ndarray | float,
    r_max: float = 100.0,
    r_min: float = 0.05,
    m_th: float = 0.50,
    n_order: float = 6.0,
) -> np.ndarray | float:
    """Chris Mack photoresist dissolution rate R(M) in nm/s."""
    m = np.clip(np.asarray(m_pac, dtype=float), 0.0, 1.0)
    if n_order <= 1.0:
        raise ValueError("Mack reaction order n_order must be > 1.0")
    a = ((n_order + 1.0) / (n_order - 1.0)) * ((1.0 - m_th) ** n_order)
    term = (1.0 - m) ** n_order
    rate = r_min + (r_max - r_min) * ((a + 1.0) * term) / (a + term)
    return float(rate) if np.ndim(rate) == 0 else rate


def tier2_process_shift(
    soft_bake_temp_c: float = 105.0,
    soft_bake_time_s: float = 60.0,
    peb_temp_c: float = 115.0,
    peb_time_s: float = 60.0,
    hard_bake_temp_c: float = 125.0,
    dev_time_s: float = 60.0,
    dev_conc_wt_pct: float = 2.38,
    dev_temp_c: float = 23.0,
    target_cd_nm: float = 45.0,
) -> Dict[str, float]:
    """Compute effective CD bias (nm) and contrast modifier from Tier 2 bake/develop variables.

    Returns process_cd_bias_nm == 0.0 and contrast_modifier == 1.0 at nominal conditions.
    """
    scale = target_cd_nm / 45.0

    # PEB: higher T/t increases acid diffusion -> Positive PR line shrinks
    l_diff = peb_diffusion_length_nm(peb_temp_c, peb_time_s)
    l_ref = peb_diffusion_length_nm(115.0, 60.0)
    peb_cd_shift = -0.32 * (l_diff - l_ref) * scale

    # Soft bake: higher T/t densifies film -> slower dissolution -> wider line CD
    sb_cd_shift = (0.14 * (soft_bake_temp_c - 105.0) + 0.015 * (soft_bake_time_s - 60.0)) * scale

    # Development: longer time, higher TMAH conc, higher temp -> faster dissolution -> narrower line CD
    dev_cd_shift = (
        -0.08 * (dev_time_s - 60.0)
        - 8.5 * (dev_conc_wt_pct - 2.38)
        - 0.35 * (dev_temp_c - 23.0)
    ) * scale

    # Hard bake > 135 C causes thermal reflow (bottom CD widening + contrast loss)
    hb_excess = max(0.0, hard_bake_temp_c - 135.0)
    hb_cd_shift = 0.25 * hb_excess * scale

    total_bias = float(peb_cd_shift + sb_cd_shift + dev_cd_shift + hb_cd_shift)

    # Contrast modifier: optimal around nominal, degrades with excessive PEB diffusion or HB reflow
    diff_ratio = l_diff / max(l_ref, 1e-6)
    contrast_mod = float(
        np.clip(
            1.0
            - 0.12 * max(0.0, diff_ratio - 1.15)
            - 0.015 * hb_excess
            + 0.15 * (dev_conc_wt_pct - 2.38),
            0.55,
            1.25,
        )
    )
    return {
        "process_cd_bias_nm": total_bias,
        "contrast_modifier": contrast_mod,
        "peb_diffusion_length_nm": l_diff,
    }


def simulate_wafer_cdu_map(
    node_key: str = "ArFi_193",
    dose_mj_cm2: Optional[float] = None,
    focus_nm: float = 0.0,
    pr_thickness_nm: Optional[float] = None,
    barc_thickness_nm: float = 40.0,
    underlayer_material: str = "Bare_Si",
    underlayer_thickness_nm: float = 100.0,
    illumination: str = "Annular",
    pattern: str = "Dense_1to1",
    peb_temp_c: float = 115.0,
    spin_accel_rpm_s: float = 10000.0,
    dispense_volume_ml: float = 2.0,
    pr_radial_range_nm: float = 3.5,
    peb_radial_range_c: float = 0.6,
    focus_noise_sigma_nm: float = 12.0,
    dose_noise_sigma_pct: float = 0.8,
    metrology_sigma_nm: float = 0.35,
    seed: int = 42,
) -> WaferCDUResult:
    """Simulate a 300 mm wafer 2D CD uniformity map with spatial coating/PEB/shot variations."""
    node = EXPOSURE_NODES[node_key]
    if node.comparison_only:
        raise ValueError(f"Node '{node_key}' is comparison-only and not supported for wafer CDU map")

    rng = np.random.default_rng(seed)
    d_pr_nom = node.default_pr_thickness_nm if pr_thickness_nm is None else float(pr_thickness_nm)
    dose_nom = node.nominal_dose_mj_cm2 if dose_mj_cm2 is None else float(dose_mj_cm2)
    t_cd = node.default_target_cd_nm

    # 300mm wafer (radius 150mm, 5mm edge exclusion -> r <= 145mm) regular die grid (15mm pitch)
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

    # Coating non-uniformity grows if dispense volume is low or spin acceleration is extreme
    coat_factor = 1.0 + max(0.0, 1.5 - dispense_volume_ml) * 0.8 + abs(spin_accel_rpm_s - 10000.0) / 25000.0
    pr_site = d_pr_nom + coat_factor * pr_radial_range_nm * (r_norm**2 - 0.5) + rng.normal(0.0, 0.4, n_sites)
    pr_site = np.maximum(pr_site, 20.0)

    # PEB hotplate radial + slight tilt gradient
    peb_site = (
        peb_temp_c
        + peb_radial_range_c * (0.5 - r_norm**2)
        + 0.20 * peb_radial_range_c * r_norm * np.cos(theta - 0.7)
        + rng.normal(0.0, 0.08, n_sites)
    )

    # Shot-to-shot focus & dose scatter
    focus_site = focus_nm + rng.normal(0.0, focus_noise_sigma_nm, n_sites)
    dose_site = dose_nom * (1.0 + rng.normal(0.0, dose_noise_sigma_pct / 100.0, n_sites))
    dose_site = np.maximum(dose_site, 1.0)

    # Pre-interpolate TMM eta_abs over the wafer PR thickness span (fast + exact)
    ambient = get_ambient_for_node(node_key)
    pr_lut = np.linspace(float(np.min(pr_site)) - 1.0, float(np.max(pr_site)) + 1.0, 25)
    eta_lut = np.empty_like(pr_lut)
    for i, d_val in enumerate(pr_lut):
        st = build_litho_stack(
            wavelength_nm=node.wavelength_nm,
            ambient_material=ambient,
            pr_thickness_nm=float(d_val),
            barc_thickness_nm=barc_thickness_nm,
            underlayer_material=underlayer_material,
            underlayer_thickness_nm=underlayer_thickness_nm,
        )
        eta_lut[i] = simulate_multilayer_optics(st, node.wavelength_nm, n_z_points=60).effective_dose_factor
    eta_site = np.interp(pr_site, pr_lut, eta_lut)

    dof_scale = float(
        depth_of_focus(
            node.wavelength_nm,
            node.na_default,
            k2=node.k2_default,
            n_fluid=node.n_fluid,
            illumination=illumination,
            pattern=pattern,
            high_na=True,
        )
    )

    cd_site = np.empty(n_sites)
    for i in range(n_sites):
        t2 = tier2_process_shift(peb_temp_c=float(peb_site[i]), target_cd_nm=t_cd)
        cd_val = float(
            bossung_cd(
                float(dose_site[i]),
                float(focus_site[i]),
                target_cd_nm=t_cd,
                nominal_dose_mj_cm2=node.nominal_dose_mj_cm2,
                dof_scale_nm=dof_scale,
                effective_dose_factor=float(eta_site[i]),
                pattern=pattern,
                illumination=illumination,
                process_cd_bias_nm=t2["process_cd_bias_nm"],
                contrast_modifier=t2["contrast_modifier"],
            )
        )
        cd_site[i] = max(0.0, cd_val + float(rng.normal(0.0, metrology_sigma_nm)))

    mean_cd = float(np.mean(cd_site))
    std_cd = float(np.std(cd_site, ddof=1))
    cdu_3s = 3.0 * std_cd
    cdu_pct = 100.0 * cdu_3s / max(t_cd, 1e-6)
    tol = t_cd * DEFECT_THRESHOLDS["cd_spec_tolerance_ratio"]
    in_spec_pct = float(100.0 * np.mean(np.abs(cd_site - t_cd) <= tol))

    return WaferCDUResult(
        node_key=node_key,
        target_cd_nm=t_cd,
        x_mm=x_mm,
        y_mm=y_mm,
        radius_mm=r_mm,
        pr_thickness_nm=pr_site,
        peb_temp_c=peb_site,
        cd_nm=cd_site,
        mean_cd_nm=mean_cd,
        std_cd_nm=std_cd,
        cdu_3sigma_nm=cdu_3s,
        cdu_3sigma_pct=cdu_pct,
        within_spec_yield_pct=in_spec_pct,
    )
