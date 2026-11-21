"""Stage 3 & 4 Matplotlib plot builders for TMM optics, BARC swing curves, and FEM/Bossung."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from src.physics.exposure_fem import FEMResult
from src.physics.optics_tmm import OpticalStackResult


def plot_standing_wave_comparison(
    res_no_barc: OpticalStackResult,
    res_with_barc: OpticalStackResult,
    underlayer_label: str = "Bare_Si",
    barc_thickness_nm: float = 40.0,
) -> Figure:
    """Compare PR internal intensity I(z) standing waves before and after BARC."""
    fig, ax = plt.subplots(figsize=(7.6, 4.5))
    ax.plot(
        res_no_barc.z_nm,
        res_no_barc.intensity_z,
        color="#d62728",
        linewidth=2.0,
        label=f"No BARC (R_sub={res_no_barc.substrate_reflectance*100:.1f}%, SWR={res_no_barc.swr_local:.2f})",
    )
    ax.plot(
        res_with_barc.z_nm,
        res_with_barc.intensity_z,
        color="#1f77b4",
        linewidth=2.2,
        label=f"BARC {barc_thickness_nm:.0f} nm (R_sub={res_with_barc.substrate_reflectance*100:.1f}%, SWR={res_with_barc.swr_local:.2f})",
    )
    ax.set_title(f"PR Internal Light Intensity I(z) Standing Wave ({underlayer_label}, λ={res_no_barc.wavelength_nm:.0f} nm)")
    ax.set_xlabel("Depth inside Photoresist z (nm) [0 = Top, d_PR = Bottom]")
    ax.set_ylabel("Normalized Optical Intensity |E(z)|^2 (a.u.)")
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.legend(frameon=True)
    fig.tight_layout()
    return fig


def plot_swing_curve_and_barc_opt(
    swing_no_barc: dict,
    swing_with_barc: dict,
    barc_opt: dict,
    underlayer_label: str = "Bare_Si",
) -> Figure:
    """Plot PR thickness Swing Curve (No BARC vs BARC) and BARC thickness optimization curve."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.2, 4.4))

    ax1.plot(
        swing_no_barc["pr_thickness_nm"],
        swing_no_barc["reflectance"] * 100.0,
        color="#d62728",
        linewidth=2.0,
        label=f"No BARC (Swing ΔR={float(swing_no_barc['reflectance_swing_amplitude'])*100:.1f}%)",
    )
    ax1.plot(
        swing_with_barc["pr_thickness_nm"],
        swing_with_barc["reflectance"] * 100.0,
        color="#1f77b4",
        linewidth=2.2,
        label=f"Optimal BARC (Swing ΔR={float(swing_with_barc['reflectance_swing_amplitude'])*100:.1f}%)",
    )
    ax1.set_title(f"Reflectivity Swing Curve ({underlayer_label})")
    ax1.set_xlabel("PR Thickness (nm)")
    ax1.set_ylabel("Total Reflectance (%)")
    ax1.grid(True, linestyle=":", alpha=0.5)
    ax1.legend(frameon=True, fontsize=8.5)

    ax2.plot(
        barc_opt["barc_thickness_nm"],
        barc_opt["substrate_reflectance"] * 100.0,
        color="#2ca02c",
        linewidth=2.2,
        label="Substrate Reflectance R_sub",
    )
    opt_d = barc_opt["optimal_barc_nm"]
    opt_r = barc_opt["min_substrate_reflectance"] * 100.0
    ax2.scatter([opt_d], [opt_r], color="#d62728", s=60, zorder=5, label=f"Optimum: {opt_d:.1f} nm ({opt_r:.2f}%)")
    ax2.axhline(2.0, color="gray", linestyle="--", linewidth=1.2, label="Target < 2%")
    ax2.set_title(f"BARC Thickness Optimization ({underlayer_label})")
    ax2.set_xlabel("BARC Thickness (nm)")
    ax2.set_ylabel("Substrate Reflectance R_sub (%)")
    ax2.grid(True, linestyle=":", alpha=0.5)
    ax2.legend(frameon=True, fontsize=8.5)

    fig.tight_layout()
    return fig


def plot_fem_heatmap_and_bossung(fem: FEMResult) -> Figure:
    """Plot 2D FEM Contour/Heatmap with Process Window rectangle + Bossung curves."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.8, 4.8))
    pw = fem.process_window

    # Panel 1: 2D FEM Heatmap + +/-10% CD contours + Max-area Process Window rectangle
    im = ax1.contourf(
        fem.focus_grid_nm,
        fem.dose_grid_mj_cm2,
        fem.cd_matrix_nm,
        levels=24,
        cmap="viridis",
    )
    fig.colorbar(im, ax=ax1, label="Printed Line CD (nm)")

    lo_cd = fem.target_cd_nm - pw.cd_tolerance_nm
    hi_cd = fem.target_cd_nm + pw.cd_tolerance_nm
    ax1.contour(
        fem.focus_grid_nm,
        fem.dose_grid_mj_cm2,
        fem.cd_matrix_nm,
        levels=[lo_cd, fem.target_cd_nm, hi_cd],
        colors=["#ff4444", "#ffffff", "#ff4444"],
        linestyles=["--", "-", "--"],
        linewidths=[1.8, 2.0, 1.8],
    )

    if pw.pw_area > 0:
        f_lo, f_hi = pw.pw_focus_bounds
        d_lo, d_hi = pw.pw_dose_bounds
        rect = Rectangle(
            (f_lo, d_lo),
            f_hi - f_lo,
            d_hi - d_lo,
            linewidth=2.2,
            edgecolor="#ffdd00",
            facecolor="none",
            label=f"PW: DOF={pw.pw_dof_nm:.0f}nm @ EL={pw.pw_el_pct:.1f}%",
        )
        ax1.add_patch(rect)
        ax1.scatter([pw.best_focus_nm], [pw.best_dose_mj_cm2], color="#ffdd00", marker="*", s=100, zorder=6)
        ax1.legend(loc="upper right", fontsize=8.5)

    ax1.set_title(f"FEM Contour & Process Window ({fem.node_key}, {fem.pattern})")
    ax1.set_xlabel("Focus / Defocus (nm)")
    ax1.set_ylabel("Exposure Dose (mJ/cm²)")

    # Panel 2: Bossung Curves (CD vs Focus for 7 representative doses)
    dose_indices = np.linspace(0, len(fem.dose_grid_mj_cm2) - 1, 7, dtype=int)
    colors = plt.cm.plasma(np.linspace(0.1, 0.88, len(dose_indices)))
    for idx, col in zip(dose_indices, colors):
        d_val = fem.dose_grid_mj_cm2[idx]
        ax2.plot(fem.focus_grid_nm, fem.cd_matrix_nm[idx], color=col, linewidth=1.8, label=f"{d_val:.1f} mJ/cm²")

    ax2.axhline(fem.target_cd_nm, color="black", linestyle="-", linewidth=1.3, label=f"Target {fem.target_cd_nm:.1f} nm")
    ax2.axhspan(lo_cd, hi_cd, color="#2ca02c", alpha=0.14, label="±10% CD Spec")
    ax2.set_title(f"Bossung Plot (BARC={fem.barc_thickness_nm:.0f}nm, η_abs={fem.optics.effective_dose_factor:.2f})")
    ax2.set_xlabel("Focus / Defocus (nm)")
    ax2.set_ylabel("Line CD (nm)")
    ax2.grid(True, linestyle=":", alpha=0.5)
    ax2.legend(loc="upper right", fontsize=7.5, ncol=2)

    fig.tight_layout()
    return fig
