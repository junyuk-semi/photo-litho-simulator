"""Stage 1 physical presets, optical constants, and parameter specifications.

All optical constants and process ranges are representative literature values
(Mack, Levinson, RefractiveIndex.INFO) for educational/portfolio simulation,
NOT proprietary semiconductor fab recipes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal, Tuple

Tier = Literal["tier1", "tier2"]
Category = Literal["optics_exposure", "pr_coating", "bake_develop", "material_underlayer"]


@dataclass(frozen=True)
class ExposureNode:
    """Representative photolithography exposure generation preset."""

    key: str
    name: str
    wavelength_nm: float
    na_default: float
    na_min: float
    na_max: float
    n_fluid: float
    k1_default: float
    k2_default: float
    nominal_dose_mj_cm2: float
    default_pr_thickness_nm: float
    default_target_cd_nm: float
    comparison_only: bool = False  # True for EUV (Stage 2 resolution/DOF comparison only)


@dataclass(frozen=True)
class IlluminationPreset:
    """Off-axis illumination (OAI) & partial coherence preset."""

    key: str
    name: str
    sigma_outer: float
    sigma_inner: float
    k1_factor: float  # Multiplicative modifier on effective k1 (<1 improves resolution)
    dof_dense_factor: float  # Multiplicative modifier on dense-pattern DOF
    dof_iso_factor: float  # Multiplicative modifier on isolated-pattern DOF


@dataclass(frozen=True)
class OpticalConstants:
    """Complex refractive index n + i*k at a specific DUV wavelength."""

    material: str
    wavelength_nm: float
    n: float
    k: float

    @property
    def n_complex(self) -> complex:
        return complex(self.n, self.k)


@dataclass(frozen=True)
class PatternPreset:
    """1D Line/Space mask pattern configuration (Positive PR baseline)."""

    key: str
    name: str
    duty_ratio: float  # Line width / Pitch (0.5 = 1:1 dense, 0.2 = isolated-like)
    bossung_base_curvature: float  # Sign/magnitude of intrinsic defocus curvature
    iso_focal_dose_ratio: float  # E_iso / E_nom


@dataclass(frozen=True)
class ParameterSpec:
    """Metadata and valid physical range for a process variable."""

    key: str
    label: str
    symbol: str
    unit: str
    category: Category
    tier: Tier
    min_val: float
    default_val: float
    max_val: float
    description: str


EXPOSURE_NODES: Dict[str, ExposureNode] = {
    "KrF_248": ExposureNode(
        key="KrF_248",
        name="KrF DUV (248 nm)",
        wavelength_nm=248.0,
        na_default=0.70,
        na_min=0.50,
        na_max=0.82,
        n_fluid=1.00,
        k1_default=0.40,
        k2_default=0.50,
        nominal_dose_mj_cm2=25.0,
        default_pr_thickness_nm=350.0,
        default_target_cd_nm=140.0,
        comparison_only=False,
    ),
    "ArF_Dry_193": ExposureNode(
        key="ArF_Dry_193",
        name="ArF Dry DUV (193 nm)",
        wavelength_nm=193.0,
        na_default=0.85,
        na_min=0.65,
        na_max=0.93,
        n_fluid=1.00,
        k1_default=0.35,
        k2_default=0.50,
        nominal_dose_mj_cm2=26.0,
        default_pr_thickness_nm=180.0,
        default_target_cd_nm=80.0,
        comparison_only=False,
    ),
    "ArFi_193": ExposureNode(
        key="ArFi_193",
        name="ArF Immersion (193 nm)",
        wavelength_nm=193.0,
        na_default=1.35,
        na_min=1.00,
        na_max=1.35,
        n_fluid=1.44,
        k1_default=0.32,
        k2_default=0.50,
        nominal_dose_mj_cm2=28.0,
        default_pr_thickness_nm=120.0,
        default_target_cd_nm=45.0,
        comparison_only=False,
    ),
    "EUV_13p5": ExposureNode(
        key="EUV_13p5",
        name="EUV (13.5 nm, Resolution/DOF Comparison Only)",
        wavelength_nm=13.5,
        na_default=0.33,
        na_min=0.25,
        na_max=0.55,
        n_fluid=1.00,
        k1_default=0.35,
        k2_default=0.50,
        nominal_dose_mj_cm2=20.0,
        default_pr_thickness_nm=35.0,
        default_target_cd_nm=14.0,
        comparison_only=True,
    ),
}


ILLUMINATION_PRESETS: Dict[str, IlluminationPreset] = {
    "Conventional": IlluminationPreset(
        key="Conventional",
        name="Conventional (Circular)",
        sigma_outer=0.70,
        sigma_inner=0.00,
        k1_factor=1.00,
        dof_dense_factor=1.00,
        dof_iso_factor=1.00,
    ),
    "Annular": IlluminationPreset(
        key="Annular",
        name="Annular OAI",
        sigma_outer=0.85,
        sigma_inner=0.55,
        k1_factor=0.90,
        dof_dense_factor=1.25,
        dof_iso_factor=0.95,
    ),
    "Dipole": IlluminationPreset(
        key="Dipole",
        name="Dipole OAI (1D Dense L/S)",
        sigma_outer=0.90,
        sigma_inner=0.65,
        k1_factor=0.82,
        dof_dense_factor=1.45,
        dof_iso_factor=0.80,
    ),
    "Quadrupole": IlluminationPreset(
        key="Quadrupole",
        name="Quadrupole OAI",
        sigma_outer=0.88,
        sigma_inner=0.60,
        k1_factor=0.86,
        dof_dense_factor=1.35,
        dof_iso_factor=0.85,
    ),
}


# Representative DUV optical constants (n, k) indexed by (material, wavelength_nm).
# c-Si ranges follow RefractiveIndex.INFO (Aspnes/Schinke); PR/BARC/Underlayers follow
# standard DUV lithography textbook ranges (Mack, Levinson).
MATERIAL_OPTICS: Dict[Tuple[str, int], OpticalConstants] = {
    # --- 193 nm (ArF / ArFi) ---
    ("Air", 193): OpticalConstants("Air", 193.0, n=1.00, k=0.00),
    ("Water_Immersion", 193): OpticalConstants("Water_Immersion", 193.0, n=1.44, k=0.00),
    ("PR_DUV", 193): OpticalConstants("PR_DUV", 193.0, n=1.70, k=0.02),
    ("BARC_Organic", 193): OpticalConstants("BARC_Organic", 193.0, n=1.75, k=0.45),
    ("SiO2", 193): OpticalConstants("SiO2", 193.0, n=1.56, k=0.00),
    ("PolySi", 193): OpticalConstants("PolySi", 193.0, n=1.15, k=2.65),
    ("Al_Metal", 193): OpticalConstants("Al_Metal", 193.0, n=0.11, k=2.20),
    ("Si_Substrate", 193): OpticalConstants("Si_Substrate", 193.0, n=1.05, k=2.90),
    # --- 248 nm (KrF) ---
    ("Air", 248): OpticalConstants("Air", 248.0, n=1.00, k=0.00),
    ("Water_Immersion", 248): OpticalConstants("Water_Immersion", 248.0, n=1.38, k=0.00),
    ("PR_DUV", 248): OpticalConstants("PR_DUV", 248.0, n=1.76, k=0.015),
    ("BARC_Organic", 248): OpticalConstants("BARC_Organic", 248.0, n=1.65, k=0.40),
    ("SiO2", 248): OpticalConstants("SiO2", 248.0, n=1.51, k=0.00),
    ("PolySi", 248): OpticalConstants("PolySi", 248.0, n=1.70, k=3.40),
    ("Al_Metal", 248): OpticalConstants("Al_Metal", 248.0, n=0.19, k=2.94),
    ("Si_Substrate", 248): OpticalConstants("Si_Substrate", 248.0, n=1.68, k=3.60),
}


PATTERN_PRESETS: Dict[str, PatternPreset] = {
    "Dense_1to1": PatternPreset(
        key="Dense_1to1",
        name="Dense 1:1 Line/Space",
        duty_ratio=0.50,
        bossung_base_curvature=0.15,
        iso_focal_dose_ratio=1.02,
    ),
    "Isolated_Line": PatternPreset(
        key="Isolated_Line",
        name="Isolated Line (1:4)",
        duty_ratio=0.20,
        bossung_base_curvature=-0.35,
        iso_focal_dose_ratio=0.92,
    ),
}


DEFECT_THRESHOLDS: Dict[str, float] = {
    "aspect_ratio_collapse_hmds": 3.0,
    "aspect_ratio_collapse_no_hmds": 2.2,
    "cd_spec_tolerance_ratio": 0.10,  # +/- 10% CD corridor for Process Window
    "scumming_dose_ratio_min": 0.75,
    "scumming_cd_ratio_max": 1.15,
    "bridging_cd_ratio_min": 0.75,
    "min_aerial_contrast": 0.25,
    "notching_reflectance_max": 0.15,  # 15% substrate reflectance
    "notching_swr_max": 2.0,  # Standing Wave Ratio I_max / I_min
}


PARAMETER_SPECS: Dict[str, ParameterSpec] = {
    # --- A. Optics & Exposure ---
    "wavelength_nm": ParameterSpec(
        "wavelength_nm", "Wavelength", "λ", "nm", "optics_exposure", "tier1",
        13.5, 193.0, 365.0, "노광 광원 파장 (본 시뮬레이터 193/248 nm, EUV 13.5 nm 비교용)",
    ),
    "na": ParameterSpec(
        "na", "Numerical Aperture", "NA", "-", "optics_exposure", "tier1",
        0.25, 1.35, 1.35, "투사 렌즈 개구수 (n*sin(theta))",
    ),
    "k1": ParameterSpec(
        "k1", "Process Factor", "k1", "-", "optics_exposure", "tier1",
        0.25, 0.32, 0.60, "Rayleigh 공정 계수 (단일 패터닝 물리 한계 ~0.25)",
    ),
    "focus_nm": ParameterSpec(
        "focus_nm", "Focus (Defocus)", "Δz", "nm", "optics_exposure", "tier1",
        -250.0, 0.0, 250.0, "최적 초점면 대비 디포커스량",
    ),
    "exposure_dose_mj_cm2": ParameterSpec(
        "exposure_dose_mj_cm2", "Exposure Dose", "E", "mJ/cm²", "optics_exposure", "tier1",
        5.0, 28.0, 60.0, "단위 면적당 노광 에너지 (Intensity * Time)",
    ),
    "light_intensity_mw_cm2": ParameterSpec(
        "light_intensity_mw_cm2", "Light Intensity", "I0", "mW/cm²", "optics_exposure", "tier1",
        10.0, 280.0, 500.0, "웨이퍼 표면 입사 광도",
    ),
    "exposure_time_s": ParameterSpec(
        "exposure_time_s", "Exposure Time", "t_exp", "s", "optics_exposure", "tier1",
        0.01, 0.10, 5.0, "노광 시간 (Dose / Intensity)",
    ),
    "illumination_sigma": ParameterSpec(
        "illumination_sigma", "Illumination Partial Coherence", "σ", "-", "optics_exposure", "tier1",
        0.20, 0.85, 0.95, "조명계 부분 간섭성 계수 (OAI 프리셋과 연동)",
    ),
    "pattern_pitch_nm": ParameterSpec(
        "pattern_pitch_nm", "Pattern Pitch", "P", "nm", "optics_exposure", "tier1",
        60.0, 90.0, 1000.0, "1D Line/Space 마스크 피치",
    ),
    # --- B. PR Coating ---
    "pr_thickness_nm": ParameterSpec(
        "pr_thickness_nm", "PR Thickness", "d_PR", "nm", "pr_coating", "tier1",
        60.0, 120.0, 1200.0, "포토레지스트 도포 두께",
    ),
    "pr_viscosity_cp": ParameterSpec(
        "pr_viscosity_cp", "PR Viscosity", "η", "cP", "pr_coating", "tier2",
        1.0, 3.0, 50.0, "포토레지스트 점도 (Meyerhofer 두께 스케일링)",
    ),
    "spin_speed_rpm": ParameterSpec(
        "spin_speed_rpm", "Spin Speed", "ω", "RPM", "pr_coating", "tier2",
        1000.0, 3000.0, 7000.0, "최종 스핀 코팅 회전 속도 (d_PR ∝ ω^-1/2)",
    ),
    "spin_accel_rpm_s": ParameterSpec(
        "spin_accel_rpm_s", "Spin Acceleration", "α_spin", "RPM/s", "pr_coating", "tier2",
        1000.0, 10000.0, 20000.0, "스핀 가속도 (코팅 균일도 및 Edge Bead 영향)",
    ),
    "spin_time_s": ParameterSpec(
        "spin_time_s", "Spin Time", "t_spin", "s", "pr_coating", "tier2",
        10.0, 45.0, 90.0, "스핀 코팅 유지 시간 (용매 증발)",
    ),
    "dispense_volume_ml": ParameterSpec(
        "dispense_volume_ml", "Dispense Volume", "V_disp", "mL", "pr_coating", "tier2",
        0.5, 2.0, 5.0, "PR 토출량 (부족 시 미도포·두께 불균일)",
    ),
    "pr_temp_c": ParameterSpec(
        "pr_temp_c", "PR Temperature", "T_PR", "°C", "pr_coating", "tier2",
        18.0, 22.0, 26.0, "PR 액온 (온도 변화에 따른 점도·두께 변동)",
    ),
    "hmds_score": ParameterSpec(
        "hmds_score", "HMDS Adhesion Condition", "HMDS", "0~1", "pr_coating", "tier2",
        0.0, 1.0, 1.0, "HMDS 표면 처리 품질 (0=미처리, 0.6=스핀, 1.0=기상)",
    ),
    # --- C. Bake & Development ---
    "soft_bake_temp_c": ParameterSpec(
        "soft_bake_temp_c", "Soft Bake Temp", "T_SB", "°C", "bake_develop", "tier2",
        80.0, 105.0, 130.0, "소프트 베이크 온도 (잔류 용매 제거, 과도 시 Scum)",
    ),
    "soft_bake_time_s": ParameterSpec(
        "soft_bake_time_s", "Soft Bake Time", "t_SB", "s", "bake_develop", "tier2",
        30.0, 60.0, 180.0, "소프트 베이크 시간",
    ),
    "peb_temp_c": ParameterSpec(
        "peb_temp_c", "PEB Temperature", "T_PEB", "°C", "bake_develop", "tier2",
        90.0, 115.0, 140.0, "노광 후 베이크 온도 (산 확산 및 정상파 완화)",
    ),
    "peb_time_s": ParameterSpec(
        "peb_time_s", "PEB Time", "t_PEB", "s", "bake_develop", "tier2",
        30.0, 60.0, 120.0, "노광 후 베이크 시간",
    ),
    "hard_bake_temp_c": ParameterSpec(
        "hard_bake_temp_c", "Hard Bake Temp", "T_HB", "°C", "bake_develop", "tier2",
        110.0, 125.0, 150.0, "하드 베이크 온도 (과도 시 PR Thermal Flow)",
    ),
    "dev_time_s": ParameterSpec(
        "dev_time_s", "Development Time", "t_dev", "s", "bake_develop", "tier2",
        15.0, 60.0, 120.0, "현상 시간",
    ),
    "dev_conc_wt_pct": ParameterSpec(
        "dev_conc_wt_pct", "Developer Concentration", "C_dev", "wt%", "bake_develop", "tier2",
        2.0, 2.38, 2.6, "TMAH 현상액 농도",
    ),
    "dev_temp_c": ParameterSpec(
        "dev_temp_c", "Developer Temperature", "T_dev", "°C", "bake_develop", "tier2",
        18.0, 23.0, 26.0, "현상액 온도",
    ),
    # --- D. Optical Properties & Underlayer ---
    "pr_n": ParameterSpec(
        "pr_n", "PR Refractive Index", "n_PR", "-", "material_underlayer", "tier1",
        1.40, 1.70, 2.10, "PR 굴절률 (정상파 주기 λ/(2n) 결정)",
    ),
    "pr_k": ParameterSpec(
        "pr_k", "PR Extinction Coeff.", "k_PR", "-", "material_underlayer", "tier1",
        0.00, 0.02, 0.20, "PR 소광계수 (흡수계수 α = 4πk/λ)",
    ),
    "barc_n": ParameterSpec(
        "barc_n", "BARC Refractive Index", "n_BARC", "-", "material_underlayer", "tier1",
        1.40, 1.75, 2.20, "BARC 굴절률",
    ),
    "barc_k": ParameterSpec(
        "barc_k", "BARC Extinction Coeff.", "k_BARC", "-", "material_underlayer", "tier1",
        0.00, 0.45, 1.00, "BARC 소광계수 (하부 반사광 감쇠)",
    ),
    "barc_thickness_nm": ParameterSpec(
        "barc_thickness_nm", "BARC Thickness", "d_BARC", "nm", "material_underlayer", "tier1",
        0.0, 40.0, 150.0, "BARC 두께 (0 nm = BARC 미적용)",
    ),
    "underlayer_thickness_nm": ParameterSpec(
        "underlayer_thickness_nm", "Underlayer Thickness", "d_UL", "nm", "material_underlayer", "tier1",
        0.0, 100.0, 500.0, "하부막(SiO2 / Poly-Si / Al) 두께",
    ),
}


def get_optical_constants(material: str, wavelength_nm: float) -> OpticalConstants:
    """Return optical constants for a material at the nearest supported DUV wavelength (193 or 248 nm)."""
    nearest_wl = 193 if abs(wavelength_nm - 193.0) <= abs(wavelength_nm - 248.0) else 248
    key = (material, nearest_wl)
    if key not in MATERIAL_OPTICS:
        available = sorted({m for m, _ in MATERIAL_OPTICS})
        raise KeyError(f"Unknown material '{material}'. Available: {available}")
    return MATERIAL_OPTICS[key]


def validate_parameter(key: str, value: float) -> float:
    """Validate that a parameter value falls within its physically defined range."""
    if key not in PARAMETER_SPECS:
        raise KeyError(f"Unknown parameter key: '{key}'")
    spec = PARAMETER_SPECS[key]
    if not (spec.min_val <= value <= spec.max_val):
        raise ValueError(
            f"Parameter '{key}'={value} out of physical range [{spec.min_val}, {spec.max_val}] {spec.unit}"
        )
    return float(value)
