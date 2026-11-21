"""Stage 3: Multilayer thin-film optics via exact 2x2 Scattering Matrix (TMM equivalent).

Uses the unconditionally stable Redheffer star product (algebraically identical to
2x2 Transfer Matrix Method) so arbitrarily thick absorbing metal layers never overflow.
Time convention: exp(-i * omega * t), complex index n_tilde = n + i * k (k >= 0).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .constants import EXPOSURE_NODES, get_optical_constants


@dataclass(frozen=True)
class LayerSpec:
    """Single homogeneous optical layer in a multilayer lithography stack."""

    name: str
    n: float
    k: float
    thickness_nm: float  # 0 or np.inf for semi-infinite ambient/substrate

    @property
    def n_complex(self) -> complex:
        return complex(self.n, self.k)


@dataclass(frozen=True)
class OpticalStackResult:
    """Computed optical properties and PR internal intensity profile."""

    wavelength_nm: float
    reflectance: float  # Total stack reflectance R (0..1)
    transmittance: float  # Poynting transmittance into substrate T (0..1)
    absorptance: float  # Total absorption in finite layers A = 1 - R - T (0..1)
    substrate_reflectance: float  # Reflectance at PR-bottom interface into underlayers (0..1)
    pr_absorption_coeff_um_inv: float  # Beer-Lambert alpha = 4*pi*k/lambda (um^-1)
    z_nm: np.ndarray  # Depth inside PR from top (0) to bottom (d_PR)
    intensity_z: np.ndarray  # Normalized optical intensity |E(z)|^2 inside PR
    swr_global: float  # max(I(z)) / min(I(z)) across PR
    swr_local: float  # Local peak-to-valley ratio around mid-PR (decoupled from attenuation)
    standing_wave_period_nm: float  # Theoretical lambda / (2 * n_PR)
    effective_dose_factor: float  # eta_abs = mean(I(z)) / mean(I_matched_ref) -> Stage 4 coupling


def _fresnel_normal(n1: complex, n2: complex) -> Tuple[complex, complex, complex, complex]:
    """Return (r12, t12, r21, t21) at normal incidence."""
    denom = n1 + n2
    r12 = (n1 - n2) / denom
    t12 = 2.0 * n1 / denom
    r21 = -r12
    t21 = 2.0 * n2 / denom
    return r12, t12, r21, t21


def _redheffer_star(
    sa: Tuple[complex, complex, complex, complex],
    sb: Tuple[complex, complex, complex, complex],
) -> Tuple[complex, complex, complex, complex]:
    """Combine two 2x2 scattering matrices (s11, s21, s12, s22) via Redheffer star product."""
    a11, a21, a12, a22 = sa
    b11, b21, b12, b22 = sb
    denom = 1.0 - a22 * b11
    s11 = a11 + (a12 * b11 * a21) / denom
    s21 = (b21 * a21) / denom
    s12 = (a12 * b12) / denom
    s22 = b22 + (b21 * a22 * b12) / denom
    return s11, s21, s12, s22


def _solve_smatrix(
    layers: Sequence[LayerSpec], wavelength_nm: float
) -> Tuple[complex, complex, complex, complex]:
    """Solve total 2x2 scattering matrix for [ambient, layer_1, ..., layer_M, substrate]."""
    if len(layers) < 2:
        raise ValueError("Stack must contain at least ambient and substrate layers")
    if wavelength_nm <= 0:
        raise ValueError("wavelength_nm must be strictly positive")

    # Start with identity scattering matrix
    s_total: Tuple[complex, complex, complex, complex] = (0j, 1.0 + 0j, 1.0 + 0j, 0j)

    for idx in range(len(layers) - 1):
        n_left = layers[idx].n_complex
        n_right = layers[idx + 1].n_complex
        r12, t12, r21, t21 = _fresnel_normal(n_left, n_right)
        s_iface = (r12, t12, t21, r21)
        s_total = _redheffer_star(s_total, s_iface)

        # Propagate across layer idx+1 if it is an internal finite layer
        if idx + 1 < len(layers) - 1:
            d_nm = layers[idx + 1].thickness_nm
            if d_nm < 0:
                raise ValueError(f"Layer '{layers[idx + 1].name}' thickness must be >= 0")
            phase = np.exp(1j * (2.0 * np.pi / wavelength_nm) * n_right * d_nm)
            s_prop = (0j, phase, phase, 0j)
            s_total = _redheffer_star(s_total, s_prop)

    return s_total


def absorption_coefficient_um_inv(k: float, wavelength_nm: float) -> float:
    """Beer-Lambert absorption coefficient alpha = 4 * pi * k / lambda (in um^-1)."""
    if wavelength_nm <= 0 or k < 0:
        raise ValueError("wavelength_nm must be > 0 and k >= 0")
    wavelength_um = wavelength_nm * 1e-3
    return float(4.0 * np.pi * k / wavelength_um)


def build_litho_stack(
    wavelength_nm: float = 193.0,
    ambient_material: str = "Water_Immersion",
    pr_thickness_nm: float = 120.0,
    barc_thickness_nm: float = 40.0,
    underlayer_material: str = "Bare_Si",
    underlayer_thickness_nm: float = 100.0,
    pr_n: Optional[float] = None,
    pr_k: Optional[float] = None,
    barc_n: Optional[float] = None,
    barc_k: Optional[float] = None,
) -> List[LayerSpec]:
    """Construct standard Ambient / PR / [BARC] / [Underlayer] / Si Substrate stack."""
    amb_opt = get_optical_constants(ambient_material, wavelength_nm)
    pr_opt = get_optical_constants("PR_DUV", wavelength_nm)
    barc_opt = get_optical_constants("BARC_Organic", wavelength_nm)
    si_opt = get_optical_constants("Si_Substrate", wavelength_nm)

    layers: List[LayerSpec] = [
        LayerSpec("Ambient", amb_opt.n, amb_opt.k, np.inf),
        LayerSpec(
            "PR",
            pr_opt.n if pr_n is None else float(pr_n),
            pr_opt.k if pr_k is None else float(pr_k),
            float(pr_thickness_nm),
        ),
    ]

    if barc_thickness_nm > 0.0:
        layers.append(
            LayerSpec(
                "BARC",
                barc_opt.n if barc_n is None else float(barc_n),
                barc_opt.k if barc_k is None else float(barc_k),
                float(barc_thickness_nm),
            )
        )

    if underlayer_material != "Bare_Si" and underlayer_thickness_nm > 0.0:
        ul_opt = get_optical_constants(underlayer_material, wavelength_nm)
        layers.append(LayerSpec(underlayer_material, ul_opt.n, ul_opt.k, float(underlayer_thickness_nm)))

    layers.append(LayerSpec("Si_Substrate", si_opt.n, si_opt.k, np.inf))
    return layers


def simulate_multilayer_optics(
    layers: Sequence[LayerSpec],
    wavelength_nm: float = 193.0,
    n_z_points: int = 200,
) -> OpticalStackResult:
    """Compute R, T, A, substrate reflectance, PR I(z), SWR, and effective dose factor eta_abs.

    Assumes layers[0] is lossless ambient (k=0) and layers[1] is the PR layer.
    """
    if len(layers) < 3:
        raise ValueError("Expected at least [Ambient, PR, Substrate] layers")
    if layers[0].k != 0.0:
        raise ValueError("Ambient medium must be lossless (k=0)")

    s_total = _solve_smatrix(layers, wavelength_nm)
    r_tot = s_total[0]
    t_tot = s_total[1]

    n0 = layers[0].n
    n_sub = layers[-1].n_complex
    reflectance = float(np.abs(r_tot) ** 2)
    transmittance = float((np.real(n_sub) / n0) * (np.abs(t_tot) ** 2))
    absorptance = float(max(0.0, 1.0 - reflectance - transmittance))

    # Sub-stack below PR: [PR (as semi-infinite incident), BARC?, Underlayer?, Substrate]
    pr_layer = layers[1]
    sub_stack = [LayerSpec("PR_inf", pr_layer.n, pr_layer.k, np.inf), *layers[2:]]
    s_below = _solve_smatrix(sub_stack, wavelength_nm)
    r_below = s_below[0]
    substrate_reflectance = float(np.abs(r_below) ** 2)

    # Exact forward and backward fields inside PR layer
    n_pr = pr_layer.n_complex
    r01, t01, r10, _ = _fresnel_normal(layers[0].n_complex, n_pr)
    k_pr = (2.0 * np.pi / wavelength_nm) * n_pr
    d_pr = pr_layer.thickness_nm

    p_pr = np.exp(1j * k_pr * d_pr)
    e_plus_0 = t01 / (1.0 - r10 * r_below * (p_pr**2))
    e_minus_d = r_below * e_plus_0 * p_pr

    z_nm = np.linspace(0.0, d_pr, n_z_points)
    e_plus_z = e_plus_0 * np.exp(1j * k_pr * z_nm)
    e_minus_z = e_minus_d * np.exp(1j * k_pr * (d_pr - z_nm))
    intensity_z = np.abs(e_plus_z + e_minus_z) ** 2

    # Matched-substrate reference (r_below = 0) for coupling factor eta_abs
    e_ref_z = t01 * np.exp(1j * k_pr * z_nm)
    mean_i_ref = float(np.mean(np.abs(e_ref_z) ** 2))
    mean_i_pr = float(np.mean(intensity_z))
    eta_abs = float(mean_i_pr / max(mean_i_ref, 1e-12))

    # Standing Wave Ratio: global and local (mid-PR decoupled from Beer-Lambert attenuation)
    i_min = float(np.min(intensity_z))
    i_max = float(np.max(intensity_z))
    swr_global = float(i_max / max(i_min, 1e-12))

    attenuation_env = np.exp(-2.0 * np.imag(k_pr) * z_nm)
    i_detrended = intensity_z / np.maximum(attenuation_env, 1e-12)
    swr_local = float(np.max(i_detrended) / max(np.min(i_detrended), 1e-12))

    sw_period = float(wavelength_nm / (2.0 * pr_layer.n))
    alpha_um = absorption_coefficient_um_inv(pr_layer.k, wavelength_nm)

    return OpticalStackResult(
        wavelength_nm=wavelength_nm,
        reflectance=reflectance,
        transmittance=transmittance,
        absorptance=absorptance,
        substrate_reflectance=substrate_reflectance,
        pr_absorption_coeff_um_inv=alpha_um,
        z_nm=z_nm,
        intensity_z=intensity_z,
        swr_global=swr_global,
        swr_local=swr_local,
        standing_wave_period_nm=sw_period,
        effective_dose_factor=eta_abs,
    )


def compute_swing_curve(
    wavelength_nm: float = 193.0,
    ambient_material: str = "Water_Immersion",
    pr_thickness_range_nm: Tuple[float, float] = (80.0, 260.0),
    n_points: int = 120,
    barc_thickness_nm: float = 0.0,
    underlayer_material: str = "Bare_Si",
    underlayer_thickness_nm: float = 100.0,
    pr_n: Optional[float] = None,
    pr_k: Optional[float] = None,
    barc_n: Optional[float] = None,
    barc_k: Optional[float] = None,
) -> Dict[str, np.ndarray]:
    """Sweep PR thickness to compute Reflectance, Effective Dose Factor, and SWR swing curves."""
    pr_grid = np.linspace(pr_thickness_range_nm[0], pr_thickness_range_nm[1], n_points)
    refl = np.empty(n_points)
    eta = np.empty(n_points)
    swr = np.empty(n_points)

    for i, d_pr in enumerate(pr_grid):
        stack = build_litho_stack(
            wavelength_nm=wavelength_nm,
            ambient_material=ambient_material,
            pr_thickness_nm=float(d_pr),
            barc_thickness_nm=barc_thickness_nm,
            underlayer_material=underlayer_material,
            underlayer_thickness_nm=underlayer_thickness_nm,
            pr_n=pr_n,
            pr_k=pr_k,
            barc_n=barc_n,
            barc_k=barc_k,
        )
        res = simulate_multilayer_optics(stack, wavelength_nm=wavelength_nm, n_z_points=80)
        refl[i] = res.reflectance
        eta[i] = res.effective_dose_factor
        swr[i] = res.swr_local

    swing_amplitude = float(np.max(refl) - np.min(refl))
    eta_swing_pct = float(100.0 * (np.max(eta) - np.min(eta)) / np.mean(eta))

    return {
        "pr_thickness_nm": pr_grid,
        "reflectance": refl,
        "effective_dose_factor": eta,
        "swr_local": swr,
        "reflectance_swing_amplitude": np.array(swing_amplitude),
        "eta_swing_pct": np.array(eta_swing_pct),
    }


def optimize_barc_thickness(
    wavelength_nm: float = 193.0,
    ambient_material: str = "Water_Immersion",
    pr_thickness_nm: float = 120.0,
    underlayer_material: str = "Bare_Si",
    underlayer_thickness_nm: float = 100.0,
    barc_range_nm: Tuple[float, float] = (0.0, 140.0),
    n_points: int = 141,
    barc_n: Optional[float] = None,
    barc_k: Optional[float] = None,
) -> Dict[str, object]:
    """Sweep BARC thickness to locate minimum substrate reflectance (first and global minima)."""
    d_grid = np.linspace(barc_range_nm[0], barc_range_nm[1], n_points)
    r_sub = np.empty(n_points)
    r_tot = np.empty(n_points)

    for i, d_barc in enumerate(d_grid):
        stack = build_litho_stack(
            wavelength_nm=wavelength_nm,
            ambient_material=ambient_material,
            pr_thickness_nm=pr_thickness_nm,
            barc_thickness_nm=float(d_barc),
            underlayer_material=underlayer_material,
            underlayer_thickness_nm=underlayer_thickness_nm,
            barc_n=barc_n,
            barc_k=barc_k,
        )
        res = simulate_multilayer_optics(stack, wavelength_nm=wavelength_nm, n_z_points=40)
        r_sub[i] = res.substrate_reflectance
        r_tot[i] = res.reflectance

    best_idx = int(np.argmin(r_sub))
    return {
        "barc_thickness_nm": d_grid,
        "substrate_reflectance": r_sub,
        "total_reflectance": r_tot,
        "optimal_barc_nm": float(d_grid[best_idx]),
        "min_substrate_reflectance": float(r_sub[best_idx]),
        "no_barc_substrate_reflectance": float(r_sub[0]),
    }


def get_ambient_for_node(node_key: str) -> str:
    """Return 'Water_Immersion' for ArFi_193 else 'Air'."""
    node = EXPOSURE_NODES[node_key]
    return "Water_Immersion" if node.n_fluid > 1.05 else "Air"
