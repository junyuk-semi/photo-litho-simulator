"""Stage 2 Matplotlib plots for Rayleigh resolution, DOF trade-off, and node comparison."""

from __future__ import annotations

from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from src.physics.constants import EXPOSURE_NODES
from src.physics.resolution import (
    compare_all_nodes,
    depth_of_focus,
    rayleigh_resolution,
    sweep_na_curve,
)


def plot_resolution_vs_na(
    k1: float = 0.35,
    illumination: str = "Conventional",
    include_euv: bool = True,
) -> Figure:
    """Plot theoretical Rayleigh CD_min vs NA across DUV (+ optional EUV comparison) nodes."""
    fig, ax = plt.subplots(figsize=(7.5, 4.8))

    configs = [
        ("KrF (248 nm)", 248.0, 0.50, 0.85, "#1f77b4", "-"),
        ("ArF Dry (193 nm)", 193.0, 0.65, 0.93, "#ff7f0e", "-"),
        ("ArF Immersion (193 nm, n=1.44)", 193.0, 0.95, 1.35, "#2ca02c", "-"),
    ]
    if include_euv:
        configs.append(("EUV (13.5 nm, comparison only)", 13.5, 0.25, 0.55, "#d62728", "--"))

    for label, wl, na_lo, na_hi, color, ls in configs:
        na_vals = np.linspace(na_lo, na_hi, 80)
        cd_vals = rayleigh_resolution(wl, na_vals, k1=k1, illumination=illumination)
        ax.plot(na_vals, cd_vals, label=label, color=color, linestyle=ls, linewidth=2.2)

    ax.set_title(f"Rayleigh Resolution vs. NA (k1={k1:.2f}, Illumination={illumination})")
    ax.set_xlabel("Numerical Aperture (NA)")
    ax.set_ylabel("Minimum Resolvable CD (nm)")
    ax.set_yscale("log")
    ax.grid(True, which="both", linestyle=":", alpha=0.5)
    ax.legend(frameon=True)
    fig.tight_layout()
    return fig


def plot_resolution_dof_tradeoff(
    wavelength_nm: float = 193.0,
    k1: float = 0.35,
    k2: float = 0.50,
    illumination: str = "Annular",
    pattern: str = "Dense_1to1",
) -> Figure:
    """Plot the NA trade-off: CD_min shrinks while DOF drops rapidly (Dry vs Immersion)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.0, 4.4))

    dry = sweep_na_curve(
        wavelength_nm, 0.55, 0.93, k1=k1, k2=k2, n_fluid=1.0,
        illumination=illumination, pattern=pattern,
    )
    imm = sweep_na_curve(
        wavelength_nm, 0.55, 1.35, k1=k1, k2=k2, n_fluid=1.44,
        illumination=illumination, pattern=pattern,
    )

    # Panel 1: CD_min and DOF vs NA
    ax1.plot(imm["na"], imm["min_cd_nm"], color="#1f77b4", linewidth=2.2, label="Min CD (nm)")
    ax1.set_xlabel("Numerical Aperture (NA)")
    ax1.set_ylabel("Minimum CD (nm)", color="#1f77b4")
    ax1.tick_params(axis="y", labelcolor="#1f77b4")
    ax1.grid(True, linestyle=":", alpha=0.5)

    ax1_r = ax1.twinx()
    ax1_r.plot(dry["na"], dry["dof_high_na_nm"], color="#ff7f0e", linestyle="--", linewidth=2.0, label="DOF Dry (n=1.0)")
    ax1_r.plot(imm["na"], imm["dof_high_na_nm"], color="#2ca02c", linewidth=2.2, label="DOF Immersion (n=1.44)")
    ax1_r.set_ylabel("Depth of Focus (nm)", color="#2ca02c")
    ax1_r.tick_params(axis="y", labelcolor="#2ca02c")
    ax1.set_title(f"CD vs. DOF Trade-off (λ={wavelength_nm:.0f} nm, {illumination})")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax1_r.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=8.5)

    # Panel 2: Direct CD vs DOF Pareto curve comparing Dry vs Immersion
    ax2.plot(dry["min_cd_nm"], dry["dof_high_na_nm"], color="#ff7f0e", linestyle="--", linewidth=2.0, label="Dry (n=1.00)")
    ax2.plot(imm["min_cd_nm"], imm["dof_high_na_nm"], color="#2ca02c", linewidth=2.2, label="Immersion (n=1.44)")
    ax2.set_xlabel("Minimum Resolvable CD (nm)")
    ax2.set_ylabel("High-NA Depth of Focus (nm)")
    ax2.set_title("Immersion DOF Gain at Equal Resolution")
    ax2.grid(True, linestyle=":", alpha=0.5)
    ax2.legend(frameon=True)

    fig.tight_layout()
    return fig


def plot_node_comparison(
    illumination: str = "Annular",
    pattern: str = "Dense_1to1",
    save_path: Optional[str] = None,
) -> Figure:
    """Compare KrF, ArF Dry, ArF Immersion, and EUV (comparison-only) presets."""
    results = compare_all_nodes(illumination=illumination, pattern=pattern)
    labels = [
        f"{r.node_key}\n(λ={r.wavelength_nm:g}nm, NA={r.na:.2f})"
        + ("\n[Comparison Only]" if r.comparison_only else "")
        for r in results
    ]
    cds = [r.min_cd_nm for r in results]
    dofs = [r.dof_high_na_nm for r in results]
    x = np.arange(len(results))
    width = 0.36

    fig, ax1 = plt.subplots(figsize=(8.6, 4.6))
    bars1 = ax1.bar(x - width / 2, cds, width, color="#1f77b4", label="Min CD (nm)")
    ax1.set_ylabel("Minimum CD (nm)", color="#1f77b4")
    ax1.tick_params(axis="y", labelcolor="#1f77b4")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=9)

    ax2 = ax1.twinx()
    bars2 = ax2.bar(x + width / 2, dofs, width, color="#2ca02c", alpha=0.85, label="High-NA DOF (nm)")
    ax2.set_ylabel("High-NA DOF (nm)", color="#2ca02c")
    ax2.tick_params(axis="y", labelcolor="#2ca02c")

    for b in bars1:
        h = b.get_height()
        ax1.text(b.get_x() + b.get_width() / 2, h + 1.5, f"{h:.1f}", ha="center", va="bottom", fontsize=8, color="#1f77b4")
    for b in bars2:
        h = b.get_height()
        ax2.text(b.get_x() + b.get_width() / 2, h + 3.0, f"{h:.0f}", ha="center", va="bottom", fontsize=8, color="#2ca02c")

    ax1.set_title(f"Lithography Node Comparison ({illumination}, {pattern})")
    ax1.grid(True, axis="y", linestyle=":", alpha=0.4)

    handles1, leg1 = ax1.get_legend_handles_labels()
    handles2, leg2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, leg1 + leg2, loc="upper right")
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig
