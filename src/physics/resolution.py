"""Stage 2: Rayleigh resolution, High-NA/Immersion DOF, OAI scaling, and exposure energy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple, Union

import numpy as np

from .constants import (
    EXPOSURE_NODES,
    ILLUMINATION_PRESETS,
    PATTERN_PRESETS,
    ExposureNode,
)

ArrayLike = Union[float, np.ndarray]
PHYSICAL_K1_SINGLE_PATTERNING_LIMIT = 0.25


@dataclass(frozen=True)
class ResolutionResult:
    """Computed optical resolution & DOF metrics for a single lithographic setup."""

    node_key: str
    node_name: str
    wavelength_nm: float
    na: float
    n_fluid: float
    illumination: str
    pattern: str
    k1_base: float
    k1_effective: float
    k2_base: float
    k2_effective: float
    min_cd_nm: float
    min_pitch_nm: float
    dof_high_na_nm: float
    dof_paraxial_nm: float
    target_cd_nm: float
    is_resolvable: bool
    resolution_margin_nm: float
    comparison_only: bool


def effective_k1(
    k1_base: float,
    illumination: str = "Conventional",
    clamp_physical_limit: bool = True,
) -> float:
    """Compute effective k1 with OAI scaling and optional single-patterning floor (>= 0.25)."""
    if k1_base <= 0:
        raise ValueError(f"k1_base must be positive, got {k1_base}")
    if illumination not in ILLUMINATION_PRESETS:
        raise KeyError(
            f"Unknown illumination '{illumination}'. Available: {list(ILLUMINATION_PRESETS)}"
        )
    k1_eff = k1_base * ILLUMINATION_PRESETS[illumination].k1_factor
    if clamp_physical_limit:
        k1_eff = max(PHYSICAL_K1_SINGLE_PATTERNING_LIMIT, k1_eff)
    return float(k1_eff)


def effective_k2(
    k2_base: float,
    illumination: str = "Conventional",
    pattern: str = "Dense_1to1",
) -> float:
    """Compute effective k2 adjusted by illumination condition and pattern density."""
    if k2_base <= 0:
        raise ValueError(f"k2_base must be positive, got {k2_base}")
    if illumination not in ILLUMINATION_PRESETS:
        raise KeyError(
            f"Unknown illumination '{illumination}'. Available: {list(ILLUMINATION_PRESETS)}"
        )
    if pattern not in PATTERN_PRESETS:
        raise KeyError(f"Unknown pattern '{pattern}'. Available: {list(PATTERN_PRESETS)}")

    preset = ILLUMINATION_PRESETS[illumination]
    factor = preset.dof_dense_factor if pattern == "Dense_1to1" else preset.dof_iso_factor
    return float(k2_base * factor)


def rayleigh_resolution(
    wavelength_nm: ArrayLike,
    na: ArrayLike,
    k1: float = 0.35,
    illumination: str = "Conventional",
    clamp_k1: bool = True,
) -> ArrayLike:
    """Rayleigh resolution: CD_min = k1_eff * wavelength / NA (nm)."""
    wl = np.asarray(wavelength_nm, dtype=float)
    na_arr = np.asarray(na, dtype=float)
    if np.any(wl <= 0):
        raise ValueError("wavelength_nm must be strictly positive")
    if np.any(na_arr <= 0):
        raise ValueError("NA must be strictly positive")

    k1_eff = effective_k1(k1, illumination=illumination, clamp_physical_limit=clamp_k1)
    cd = k1_eff * wl / na_arr
    return float(cd) if np.ndim(cd) == 0 else cd


def depth_of_focus(
    wavelength_nm: ArrayLike,
    na: ArrayLike,
    k2: float = 0.50,
    n_fluid: float = 1.0,
    illumination: str = "Conventional",
    pattern: str = "Dense_1to1",
    high_na: bool = True,
) -> ArrayLike:
    """Compute optical Depth of Focus (nm).

    Paraxial: DOF = k2_eff * n_fluid * wavelength / NA^2
    High-NA:  DOF = (k2_eff / 2) * wavelength / (n_fluid - sqrt(n_fluid^2 - NA^2))
    Both expressions converge identically as NA -> 0.
    """
    wl = np.asarray(wavelength_nm, dtype=float)
    na_arr = np.asarray(na, dtype=float)
    if np.any(wl <= 0):
        raise ValueError("wavelength_nm must be strictly positive")
    if np.any(na_arr <= 0):
        raise ValueError("NA must be strictly positive")
    if n_fluid <= 0:
        raise ValueError("n_fluid must be strictly positive")
    if high_na and np.any(na_arr >= n_fluid):
        raise ValueError(f"NA must be strictly less than n_fluid ({n_fluid}) for high-NA DOF")

    k2_eff = effective_k2(k2, illumination=illumination, pattern=pattern)
    if high_na:
        denom = n_fluid - np.sqrt(n_fluid**2 - na_arr**2)
        dof = 0.5 * k2_eff * wl / denom
    else:
        dof = k2_eff * n_fluid * wl / (na_arr**2)

    return float(dof) if np.ndim(dof) == 0 else dof


def exposure_dose(light_intensity_mw_cm2: ArrayLike, exposure_time_s: ArrayLike) -> ArrayLike:
    """Compute exposure dose E = I0 * t_exp (mJ/cm^2 = mW/cm^2 * s)."""
    i0 = np.asarray(light_intensity_mw_cm2, dtype=float)
    t = np.asarray(exposure_time_s, dtype=float)
    if np.any(i0 < 0) or np.any(t < 0):
        raise ValueError("light_intensity and exposure_time must be non-negative")
    dose = i0 * t
    return float(dose) if np.ndim(dose) == 0 else dose


def required_exposure_time(
    target_dose_mj_cm2: ArrayLike, light_intensity_mw_cm2: ArrayLike
) -> ArrayLike:
    """Compute required exposure time t_exp = Dose / I0 (s)."""
    dose = np.asarray(target_dose_mj_cm2, dtype=float)
    i0 = np.asarray(light_intensity_mw_cm2, dtype=float)
    if np.any(dose < 0):
        raise ValueError("target_dose_mj_cm2 must be non-negative")
    if np.any(i0 <= 0):
        raise ValueError("light_intensity_mw_cm2 must be strictly positive")
    t = dose / i0
    return float(t) if np.ndim(t) == 0 else t


def analyze_node(
    node_key: str,
    na: Optional[float] = None,
    k1: Optional[float] = None,
    k2: Optional[float] = None,
    illumination: str = "Conventional",
    pattern: str = "Dense_1to1",
    target_cd_nm: Optional[float] = None,
) -> ResolutionResult:
    """Evaluate Rayleigh resolution, High-NA/paraxial DOF, and resolvability for a node preset."""
    if node_key not in EXPOSURE_NODES:
        raise KeyError(f"Unknown node '{node_key}'. Available: {list(EXPOSURE_NODES)}")

    node: ExposureNode = EXPOSURE_NODES[node_key]
    na_val = node.na_default if na is None else float(na)
    k1_val = node.k1_default if k1 is None else float(k1)
    k2_val = node.k2_default if k2 is None else float(k2)
    target_val = node.default_target_cd_nm if target_cd_nm is None else float(target_cd_nm)

    k1_eff = effective_k1(k1_val, illumination=illumination, clamp_physical_limit=True)
    k2_eff = effective_k2(k2_val, illumination=illumination, pattern=pattern)
    min_cd = float(
        rayleigh_resolution(node.wavelength_nm, na_val, k1=k1_val, illumination=illumination)
    )
    dof_hi = float(
        depth_of_focus(
            node.wavelength_nm,
            na_val,
            k2=k2_val,
            n_fluid=node.n_fluid,
            illumination=illumination,
            pattern=pattern,
            high_na=True,
        )
    )
    dof_par = float(
        depth_of_focus(
            node.wavelength_nm,
            na_val,
            k2=k2_val,
            n_fluid=node.n_fluid,
            illumination=illumination,
            pattern=pattern,
            high_na=False,
        )
    )

    duty = PATTERN_PRESETS[pattern].duty_ratio
    min_pitch = min_cd / duty
    margin = target_val - min_cd

    return ResolutionResult(
        node_key=node.key,
        node_name=node.name,
        wavelength_nm=node.wavelength_nm,
        na=na_val,
        n_fluid=node.n_fluid,
        illumination=illumination,
        pattern=pattern,
        k1_base=k1_val,
        k1_effective=k1_eff,
        k2_base=k2_val,
        k2_effective=k2_eff,
        min_cd_nm=min_cd,
        min_pitch_nm=min_pitch,
        dof_high_na_nm=dof_hi,
        dof_paraxial_nm=dof_par,
        target_cd_nm=target_val,
        is_resolvable=(margin >= 0.0),
        resolution_margin_nm=margin,
        comparison_only=node.comparison_only,
    )


def compare_all_nodes(
    illumination: str = "Conventional",
    pattern: str = "Dense_1to1",
) -> List[ResolutionResult]:
    """Compare KrF, ArF Dry, ArF Immersion, and EUV (comparison-only) presets."""
    return [
        analyze_node(key, illumination=illumination, pattern=pattern)
        for key in ("KrF_248", "ArF_Dry_193", "ArFi_193", "EUV_13p5")
    ]


def sweep_na_curve(
    wavelength_nm: float,
    na_min: float,
    na_max: float,
    n_points: int = 80,
    k1: float = 0.35,
    k2: float = 0.50,
    n_fluid: float = 1.0,
    illumination: str = "Conventional",
    pattern: str = "Dense_1to1",
) -> Dict[str, np.ndarray]:
    """Generate NA sweep arrays for CD_min and High-NA/Paraxial DOF."""
    if n_points < 2:
        raise ValueError("n_points must be >= 2")
    na_grid = np.linspace(na_min, na_max, n_points)
    cd_grid = np.asarray(
        rayleigh_resolution(wavelength_nm, na_grid, k1=k1, illumination=illumination),
        dtype=float,
    )
    dof_hi_grid = np.asarray(
        depth_of_focus(
            wavelength_nm,
            na_grid,
            k2=k2,
            n_fluid=n_fluid,
            illumination=illumination,
            pattern=pattern,
            high_na=True,
        ),
        dtype=float,
    )
    dof_par_grid = np.asarray(
        depth_of_focus(
            wavelength_nm,
            na_grid,
            k2=k2,
            n_fluid=n_fluid,
            illumination=illumination,
            pattern=pattern,
            high_na=False,
        ),
        dtype=float,
    )
    return {
        "na": na_grid,
        "min_cd_nm": cd_grid,
        "dof_high_na_nm": dof_hi_grid,
        "dof_paraxial_nm": dof_par_grid,
    }


def sweep_wavelength_na_grid(
    wavelengths_nm: Iterable[float],
    na_values: Iterable[float],
    k1: float = 0.35,
    illumination: str = "Conventional",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute 2D meshgrid of Rayleigh CD_min(wavelength, NA)."""
    wl_arr = np.asarray(list(wavelengths_nm), dtype=float)
    na_arr = np.asarray(list(na_values), dtype=float)
    wl_mesh, na_mesh = np.meshgrid(wl_arr, na_arr, indexing="ij")
    cd_mesh = np.asarray(
        rayleigh_resolution(wl_mesh, na_mesh, k1=k1, illumination=illumination),
        dtype=float,
    )
    return wl_mesh, na_mesh, cd_mesh
