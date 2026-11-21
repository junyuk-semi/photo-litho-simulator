"""Intuitive physical schematic & visual diagram builders for Study Mode (Pages 1-4)."""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.patches import Arc, FancyArrowPatch, Polygon, Rectangle

from src.physics.exposure_fem import FEMResult
from src.physics.optics_tmm import LayerSpec, OpticalStackResult


def plot_rayleigh_aperture_intuition(
    wavelength_nm: float,
    na: float,
    n_fluid: float,
    illumination: str,
    min_cd_nm: float,
    target_cd_nm: float,
    dof_nm: float,
) -> Figure:
    """Visualize NA acceptance cone, immersion refraction, DOF waist, and brush-size analogy."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.2, 4.2))

    # --- Panel 1: Lens Acceptance Cone & DOF Focus Waist ---
    sin_theta = min(0.985, na / max(n_fluid, 1.0))
    theta_rad = float(np.arcsin(sin_theta))
    theta_deg = float(np.degrees(theta_rad))

    # Ambient fill above wafer
    if n_fluid > 1.05:
        ax1.axhspan(0.0, 0.72, color="#d0ebff", alpha=0.45, label=f"Water Immersion (n={n_fluid:.2f})")
    else:
        ax1.axhspan(0.0, 0.72, color="#f8f9fa", alpha=0.5, label=f"Air Ambient (n={n_fluid:.2f})")

    # Wafer & PR at bottom
    ax1.add_patch(Rectangle((-1.2, -0.18), 2.4, 0.18, color="#868e96", alpha=0.7))
    ax1.text(0, -0.10, "Wafer / Photoresist", ha="center", va="center", color="white", fontsize=8.5, fontweight="bold")

    # Lens arc at top
    lens_y = 0.85
    lens_w = max(0.35, min(1.05, 0.95 * np.tan(theta_rad) * lens_y))
    ax1.plot([-lens_w, lens_w], [lens_y, lens_y], color="#1971c2", linewidth=6, solid_capstyle="round")
    ax1.text(0, lens_y + 0.08, f"Projection Lens (NA = {na:.2f}, θ = {theta_deg:.1f}°)", ha="center", fontsize=9, fontweight="bold", color="#1864ab")

    # Rays converging to focus (0, 0)
    ray_color = "#2b8a3e" if illumination != "Conventional" else "#e67700"
    ax1.plot([-lens_w, 0, lens_w * 0.28], [lens_y, 0, -0.15], color=ray_color, linewidth=2.0)
    ax1.plot([lens_w, 0, -lens_w * 0.28], [lens_y, 0, -0.15], color=ray_color, linewidth=2.0)
    if illumination != "Conventional":
        # OAI oblique illumination rays
        ax1.annotate("", xy=(-0.15, 0.02), xytext=(-lens_w * 0.78, lens_y), arrowprops=dict(arrowstyle="->", color="#d6336c", lw=1.6, ls="--"))
        ax1.annotate("", xy=(0.15, 0.02), xytext=(lens_w * 0.78, lens_y), arrowprops=dict(arrowstyle="->", color="#d6336c", lw=1.6, ls="--"))
        ax1.text(0, 0.56, f"OAI ({illumination}): Oblique rays catch 1st-order diffraction", ha="center", fontsize=8, color="#a61e4d", bbox=dict(boxstyle="round,pad=0.2", fc="#fff0f6", ec="#faa2c1"))

    # DOF waist band around focus
    dof_vis = float(np.clip(dof_nm / 900.0, 0.03, 0.22))
    ax1.axhspan(0.0, dof_vis, color="#51cf66", alpha=0.35)
    ax1.annotate(
        f"DOF Margin = {dof_nm:.0f} nm\n(Larger NA -> Thinner Waist!)",
        xy=(0.18, dof_vis * 0.5),
        xytext=(0.45, 0.25),
        arrowprops=dict(arrowstyle="->", color="#2b8a3e", lw=1.3),
        fontsize=8,
        color="#2b8a3e",
        fontweight="bold",
    )

    ax1.add_patch(Arc((0, 0), 0.55, 0.55, angle=90, theta1=-theta_deg, theta2=theta_deg, color="#1971c2", lw=1.5))
    ax1.set_xlim(-1.2, 1.2)
    ax1.set_ylim(-0.22, 1.05)
    ax1.set_xticks([])
    ax1.set_yticks([])
    ax1.set_title("1) Optical Cone & Depth of Focus (Camera Aperture Analogy)")

    # --- Panel 2: Brush-Width (λ) & Target CD Resolvability ---
    items = ["Light Wavelength\n(λ, Brush Size)", "Min Resolvable CD\n(CD_min = k1*λ/NA)", "Your Target CD\n(Line Width)"]
    vals = [wavelength_nm, min_cd_nm, target_cd_nm]
    colors = ["#748ffc", "#ff922b" if min_cd_nm > target_cd_nm else "#51cf66", "#228be6"]
    bars = ax2.barh(items[::-1], vals[::-1], color=colors[::-1], height=0.48, alpha=0.9)
    for b in bars:
        w = b.get_width()
        ax2.text(w + max(vals) * 0.02, b.get_y() + b.get_height() / 2, f"{w:.1f} nm", va="center", fontsize=9, fontweight="bold")
    ax2.set_xlim(0, max(vals) * 1.28)
    pass_txt = "PASS: Target >= CD_min" if target_cd_nm >= min_cd_nm else "FAIL: Diffraction Blurs Pattern!"
    pass_col = "#2b8a3e" if target_cd_nm >= min_cd_nm else "#c92a2a"
    ax2.set_title(f"2) Brush Size vs Target Line Width ({pass_txt})", color=pass_col)
    ax2.set_xlabel("Dimension (nm)")
    ax2.grid(True, axis="x", linestyle=":", alpha=0.45)

    fig.tight_layout()
    return fig


def plot_multilayer_stack_intuition(
    layers: list[LayerSpec],
    res_off: OpticalStackResult,
    res_on: OpticalStackResult,
    barc_thickness_nm: float,
) -> Figure:
    """Visualize multilayer stack cross-section, energy split (R/A/T) & PR sidewall standing waves."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.2, 4.4))

    # --- Panel 1: Stack Cross-Section & Ray Reflection Arrows ---
    palette = {
        "Ambient": "#e7f5ff",
        "PR": "#ffd8a8",
        "BARC": "#d0bfff",
        "SiO2": "#c5f6fa",
        "PolySi": "#ffe066",
        "Al_Metal": "#ced4da",
        "Si_Substrate": "#868e96",
    }
    # Build visual heights (proportional within reasonable bounds)
    y_cursor = 1.0
    vis_heights = []
    for lyr in layers:
        if np.isinf(lyr.thickness_nm):
            h = 0.22
        else:
            h = float(np.clip(lyr.thickness_nm / 300.0, 0.09, 0.34))
        vis_heights.append(h)
    total_h = sum(vis_heights)
    y_cursor = total_h
    pr_y_range = (0.0, 0.5)

    for lyr, h in zip(layers, vis_heights):
        y_bot = y_cursor - h
        col = palette.get(lyr.name, "#dee2e6")
        ax1.add_patch(Rectangle((0.0, y_bot), 1.0, h, facecolor=col, edgecolor="#495057", linewidth=1.0))
        thick_lbl = "Semi-inf" if np.isinf(lyr.thickness_nm) else f"{lyr.thickness_nm:.0f} nm"
        txt_col = "white" if lyr.name == "Si_Substrate" else "#212529"
        ax1.text(0.50, y_bot + h / 2, f"{lyr.name} ({thick_lbl}, n={lyr.n:.2f}, k={lyr.k:.2f})", ha="center", va="center", fontsize=8.0, color=txt_col, fontweight="bold")
        if lyr.name == "PR":
            pr_y_range = (y_bot, y_cursor)
        y_cursor = y_bot

    # Incident ray (100%)
    ax1.add_patch(FancyArrowPatch((0.20, total_h - 0.02), (0.20, pr_y_range[0]), arrowstyle="-|>", mutation_scale=15, linewidth=3.2, color="#1971c2"))
    ax1.text(0.18, total_h - 0.06, "Incident 100%", ha="right", va="top", fontsize=8, color="#1971c2", fontweight="bold")

    # Reflected ray back up from bottom (proportional to R_sub)
    r_sub_pct = res_on.substrate_reflectance * 100.0
    lw_ref = max(0.8, min(4.5, 0.8 + r_sub_pct / 10.0))
    ref_col = "#d62728" if r_sub_pct > 5.0 else "#2b8a3e"
    ax1.add_patch(FancyArrowPatch((0.80, pr_y_range[0]), (0.80, total_h - 0.02), arrowstyle="-|>", mutation_scale=15, linewidth=lw_ref, color=ref_col))
    ax1.text(0.83, pr_y_range[1] - 0.05, f"Bounce R_sub\n{r_sub_pct:.2f}%", ha="left", va="center", fontsize=8.5, color=ref_col, fontweight="bold")

    ax1.set_xlim(0.0, 1.0)
    ax1.set_ylim(0.0, total_h)
    ax1.set_xticks([])
    ax1.set_yticks([])
    ax1.set_title(
        f"1) Stack Optical Path (R={res_on.reflectance*100:.1f}%, A={res_on.absorptance*100:.1f}%, T={res_on.transmittance*100:.1f}%)"
    )

    # --- Panel 2: Resulting PR Sidewall Standing-Wave Profile Sketch ---
    z_norm = np.linspace(0, 1, 200)
    # Normalize intensities to sketch how sidewall ripples scale with SWR
    amp_off = min(0.28, 0.06 * max(0.0, res_off.swr_local - 1.0))
    amp_on = min(0.28, 0.06 * max(0.0, res_on.swr_local - 1.0))
    cycles = max(2.0, res_off.z_nm[-1] / max(res_off.standing_wave_period_nm, 1.0))

    wall_off = 0.35 + amp_off * np.cos(2 * np.pi * cycles * z_norm)
    wall_on = 0.35 + amp_on * np.cos(2 * np.pi * cycles * z_norm)

    # Left half: No BARC, Right half: With BARC
    ax2.fill_betweenx(z_norm, 0.15, 0.15 + wall_off * 0.55, color="#ffa8a8", alpha=0.8, label=f"No BARC (SWR={res_off.swr_local:.2f})")
    ax2.plot(0.15 + wall_off * 0.55, z_norm, color="#d62728", linewidth=2.0)

    ax2.fill_betweenx(z_norm, 0.60, 0.60 + wall_on * 0.55, color="#a5d8ff", alpha=0.85, label=f"BARC {barc_thickness_nm:.0f}nm (SWR={res_on.swr_local:.2f})")
    ax2.plot(0.60 + wall_on * 0.55, z_norm, color="#1971c2", linewidth=2.2)

    ax2.invert_yaxis()
    ax2.set_xlim(0.05, 1.05)
    ax2.set_xticks([0.28, 0.73])
    ax2.set_xticklabels(["Without BARC\n(Wavy Sidewall)", f"With BARC ({barc_thickness_nm:.0f}nm)\n(Smooth Vertical Wall)"])
    ax2.set_ylabel("PR Depth (0 = Top -> 1 = Bottom)")
    ax2.set_title("2) Standing Wave Effect on PR Sidewall Shape")
    ax2.legend(loc="lower right", fontsize=8)
    ax2.grid(True, axis="y", linestyle=":", alpha=0.4)

    fig.tight_layout()
    return fig


def plot_pr_profile_and_defects_intuition(fem: FEMResult) -> Figure:
    """Visualize expected PR line cross-section geometry & 4 defect gauges at PW center."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.2, 4.0))
    dfct = fem.defects_at_center
    flags = set(dfct.flags)

    # Substrate base
    ax1.add_patch(Rectangle((0, 0), 1.0, 0.14, color="#868e96"))
    ax1.text(0.5, 0.07, f"Substrate ({fem.underlayer}, BARC={fem.barc_thickness_nm:.0f} nm)", ha="center", va="center", color="white", fontsize=8.5, fontweight="bold")

    # PR Line polygon reflecting current defects
    x_c = 0.50
    half_w = 0.16
    if "Bridging/Pinching" in flags:
        half_w = 0.08
    elif "Scumming" in flags:
        half_w = 0.22

    h_pr = min(0.75, max(0.32, 0.20 * dfct.aspect_ratio))
    lean = 0.14 if "Pattern Collapse" in flags else 0.0

    # Build left & right walls
    ys = np.linspace(0.14, 0.14 + h_pr, 40)
    notch = 0.045 if "Reflective Notching" in flags else 0.008 * max(0.0, fem.optics.swr_local - 1.0)
    notch = min(0.055, notch)
    ripple = notch * np.sin(5 * np.pi * (ys - 0.14) / h_pr)
    tilt = lean * ((ys - 0.14) / h_pr) ** 1.4

    x_left = x_c - half_w + tilt + np.abs(ripple) * (0.6 if "Reflective Notching" in flags else 0.2)
    x_right = x_c + half_w + tilt - np.abs(ripple) * (0.6 if "Reflective Notching" in flags else 0.2)
    pts = list(zip(x_left, ys)) + list(zip(x_right[::-1], ys[::-1]))
    pr_col = "#ff8787" if flags else "#4dabf7"
    ax1.add_patch(Polygon(pts, closed=True, facecolor=pr_col, edgecolor="#1c7ed6" if not flags else "#c92a2a", linewidth=2.0, alpha=0.88))

    if "Scumming" in flags:
        ax1.add_patch(Rectangle((0.05, 0.14), 0.90, 0.05, color="#ffa94d", alpha=0.75))
        ax1.text(0.22, 0.21, "Scum Residue!", color="#d9480f", fontsize=8.5, fontweight="bold")
    if "Pattern Collapse" in flags:
        ax1.text(x_c + 0.20, 0.14 + h_pr * 0.8, f"Leaning / Collapse!\n(AR={dfct.aspect_ratio:.2f})", color="#c92a2a", fontsize=8.5, fontweight="bold")
    if "Reflective Notching" in flags:
        ax1.text(0.10, 0.14 + h_pr * 0.45, f"Notching!\n(SWR={fem.optics.swr_local:.2f})", color="#c92a2a", fontsize=8.5, fontweight="bold")
    if not flags:
        ax1.text(x_c, 0.14 + h_pr + 0.06, f"Healthy PR Profile (AR={dfct.aspect_ratio:.2f})", ha="center", color="#2b8a3e", fontsize=9, fontweight="bold")

    ax1.set_xlim(0, 1.0)
    ax1.set_ylim(0, 1.05)
    ax1.set_xticks([])
    ax1.set_yticks([])
    ax1.set_title("1) Schematic PR Cross-Section at Current Condition")

    # --- Panel 2: 4 Defect Risk Scores ---
    names = ["Pattern Collapse\n(Domino Fall)", "Scumming\n(Unwashed Residue)", "Bridging/Pinching\n(Short / Break)", "Reflective Notching\n(Mirror Bounce)"]
    scores = [dfct.pattern_collapse_risk, dfct.scumming_risk, dfct.bridging_pinching_risk, dfct.notching_risk]
    bar_cols = ["#d62728" if s >= 50 else ("#ff922b" if s >= 25 else "#51cf66") for s in scores]
    bars = ax2.barh(names[::-1], scores[::-1], color=bar_cols[::-1], height=0.52, alpha=0.9)
    ax2.axvline(50.0, color="#d62728", linestyle="--", linewidth=1.2, label="High Risk (>=50)")
    for b in bars:
        w = b.get_width()
        ax2.text(w + 1.5, b.get_y() + b.get_height() / 2, f"{w:.1f}", va="center", fontsize=8.5, fontweight="bold")
    ax2.set_xlim(0, 115)
    ax2.set_title("2) 4 Major Lithography Defect Risk Gauges")
    ax2.set_xlabel("Risk Score (0 = Safe, 100 = Severe)")
    ax2.legend(loc="lower right", fontsize=8)
    ax2.grid(True, axis="x", linestyle=":", alpha=0.45)

    fig.tight_layout()
    return fig


def plot_cdu_radial_decomposition(cdu) -> Figure:
    """Plot wafer center-to-edge radial profiles (PR Thickness, PEB Temp, CD) to explain edge yield loss."""
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 3.6))
    r = cdu.radius_mm

    axes[0].scatter(r, cdu.pr_thickness_nm, s=16, alpha=0.75, color="#1971c2")
    axes[0].set_title("1) Spin-Coat PR Thickness vs Radius")
    axes[0].set_xlabel("Radius r (mm) [0=Center -> 145=Edge]")
    axes[0].set_ylabel("PR Thickness (nm)")
    axes[0].grid(True, linestyle=":", alpha=0.5)

    axes[1].scatter(r, cdu.peb_temp_c, s=16, alpha=0.75, color="#e8590c")
    axes[1].set_title("2) Hotplate PEB Temp vs Radius")
    axes[1].set_xlabel("Radius r (mm)")
    axes[1].set_ylabel("PEB Temp (°C)")
    axes[1].grid(True, linestyle=":", alpha=0.5)

    axes[2].scatter(r, cdu.cd_nm, s=16, alpha=0.75, color="#2b8a3e")
    axes[2].axhline(cdu.target_cd_nm, color="black", linestyle="-", lw=1.2, label="Target")
    axes[2].axhline(cdu.target_cd_nm * 0.9, color="#d62728", linestyle="--", lw=1.2, label="±10% Spec")
    axes[2].axhline(cdu.target_cd_nm * 1.1, color="#d62728", linestyle="--", lw=1.2)
    axes[2].set_title("3) Resulting CD vs Radius (Edge Drift)")
    axes[2].set_xlabel("Radius r (mm)")
    axes[2].set_ylabel("CD (nm)")
    axes[2].legend(fontsize=8)
    axes[2].grid(True, linestyle=":", alpha=0.5)

    fig.tight_layout()
    return fig
