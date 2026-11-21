"""Matplotlib visualizations for the Real-World Fab Run-to-Run Yield Improvement Cycle."""

from __future__ import annotations

from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Circle

from src.fab_cycle import CycleResult


def plot_cycle_progression(history: Sequence[CycleResult]) -> Figure:
    """Plot 4-panel KPI progression across Simulation Cycles (1 -> 2 -> 3 -> ...)."""
    cycles = [f"Cycle {c.cycle_id}" for c in history]
    x = np.arange(len(history))

    aci_yield = [c.aci_yield_pct for c in history]
    adi_yield = [c.adi_yield_pct for c in history]
    cdu_3s = [c.aci_cdu_3sigma_nm for c in history]
    r_sub = [c.optics.substrate_reflectance * 100.0 for c in history]
    defect_risk = [c.defects_operating.overall_defect_risk for c in history]
    aci_mean = [c.aci_mean_cd_nm for c in history]
    target_cd = history[-1].target_aci_cd_nm

    fig, axes = plt.subplots(2, 2, figsize=(11.4, 7.2))
    ax1, ax2, ax3, ax4 = axes.flat

    # Panel 1: Yield progression
    ax1.plot(x, aci_yield, marker="o", linewidth=2.4, color="#2ca02c", label="ACI Yield (%)")
    ax1.plot(x, adi_yield, marker="s", linewidth=1.8, linestyle="--", color="#1f77b4", label="ADI Yield (%)")
    ax1.axhline(95.0, color="gray", linestyle=":", linewidth=1.2, label="Target >= 95%")
    for xi, yi in zip(x, aci_yield):
        ax1.annotate(f"{yi:.1f}%", (xi, yi), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=8.5, fontweight="bold")
    ax1.set_ylim(0, 112)
    ax1.set_xticks(x)
    ax1.set_xticklabels(cycles)
    ax1.set_title("Wafer Yield Improvement Across Cycles")
    ax1.set_ylabel("In-Spec Yield (%)")
    ax1.grid(True, linestyle=":", alpha=0.5)
    ax1.legend(loc="lower right", fontsize=8.5)

    # Panel 2: CDU 3-sigma reduction
    ax2.bar(x, cdu_3s, width=0.45, color="#ff7f0e", alpha=0.88, label="ACI CDU 3σ (nm)")
    ax2.axhline(target_cd * 0.03, color="#2ca02c", linestyle="--", linewidth=1.4, label="Target <= 3% CD")
    for xi, val in zip(x, cdu_3s):
        ax2.text(xi, val + 0.15, f"{val:.2f}", ha="center", va="bottom", fontsize=8.5)
    ax2.set_xticks(x)
    ax2.set_xticklabels(cycles)
    ax2.set_title("300mm Wafer CDU (3σ) Reduction")
    ax2.set_ylabel("CDU 3σ (nm)")
    ax2.grid(True, axis="y", linestyle=":", alpha=0.5)
    ax2.legend(fontsize=8.5)

    # Panel 3: Substrate Reflectance & Defect Risk
    ax3.plot(x, r_sub, marker="o", linewidth=2.2, color="#d62728", label="Substrate Reflectance R_sub (%)")
    ax3.plot(x, defect_risk, marker="^", linewidth=2.0, color="#9467bd", label="Defect Risk Score (0-100)")
    ax3.axhline(2.0, color="#d62728", linestyle=":", linewidth=1.1, label="R_sub Target < 2%")
    ax3.set_xticks(x)
    ax3.set_xticklabels(cycles)
    ax3.set_title("Optical Reflection & Defect Risk Suppression")
    ax3.set_ylabel("Percent / Score")
    ax3.grid(True, linestyle=":", alpha=0.5)
    ax3.legend(fontsize=8.0)

    # Panel 4: ACI Mean CD Convergence to Target
    ax4.plot(x, aci_mean, marker="D", linewidth=2.2, color="#1f77b4", label="Mean ACI CD (nm)")
    ax4.axhspan(target_cd * 0.9, target_cd * 1.1, color="#2ca02c", alpha=0.14, label="±10% Spec Window")
    ax4.axhline(target_cd, color="black", linestyle="--", linewidth=1.3, label=f"Target {target_cd:.1f} nm")
    for xi, val in zip(x, aci_mean):
        ax4.annotate(f"{val:.2f}", (xi, val), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=8.5)
    ax4.set_xticks(x)
    ax4.set_xticklabels(cycles)
    ax4.set_title("Mean ACI CD Convergence to Target")
    ax4.set_ylabel("ACI CD (nm)")
    ax4.grid(True, linestyle=":", alpha=0.5)
    ax4.legend(fontsize=8.0)

    fig.tight_layout()
    return fig


def plot_cycle_wafer_comparison(history: Sequence[CycleResult]) -> Figure:
    """Compare up to the latest 4 cycles' 300mm wafer ACI CD maps side-by-side."""
    shown = list(history[-4:])
    n = len(shown)
    fig, axes = plt.subplots(1, n, figsize=(3.9 * n, 4.2), squeeze=False, layout="constrained")

    target_cd = shown[-1].target_aci_cd_nm
    vmin = target_cd * 0.85
    vmax = target_cd * 1.15

    last_sc = None
    for idx, c in enumerate(shown):
        ax = axes[0, idx]
        ax.add_patch(Circle((0, 0), 150.0, fill=False, edgecolor="black", linewidth=1.6))
        last_sc = ax.scatter(
            c.wafer_cdu.x_mm,
            c.wafer_cdu.y_mm,
            c=c.aci_cd_sites_nm,
            cmap="coolwarm",
            vmin=vmin,
            vmax=vmax,
            s=36,
            marker="s",
            edgecolors="none",
        )
        ax.set_xlim(-160, 160)
        ax.set_ylim(-160, 160)
        ax.set_aspect("equal")
        ax.set_title(
            f"Cycle {c.cycle_id} (BARC={c.recipe.barc_thickness_nm:.0f}nm)\n"
            f"ACI Yield={c.aci_yield_pct:.1f}% | 3σ={c.aci_cdu_3sigma_nm:.2f}nm",
            fontsize=9.2,
        )
        ax.set_xlabel("X (mm)", fontsize=8.5)
        if idx == 0:
            ax.set_ylabel("Y (mm)", fontsize=8.5)
        ax.grid(True, linestyle=":", alpha=0.35)

    if last_sc is not None:
        fig.colorbar(last_sc, ax=axes.ravel().tolist(), shrink=0.82, label="ACI CD (nm)")
    fig.suptitle(f"300mm Wafer ACI CD Map Progression (Target = {target_cd:.1f} nm ±10%)", fontsize=11)
    return fig


def plot_root_cause_pareto(cycle: CycleResult) -> Figure:
    """Plot horizontal bar chart of root-cause RMS error and variance share for one cycle."""
    rows = list(reversed(cycle.variance_breakdown))
    labels = [
        f"Cause {len(rows) - i}"
        for i in range(len(rows))
    ]
    # Use concise English-safe tags inside figure, full Korean details in table/report
    short_map = {
        "평균 Dose / Etch Bias 타겟 오프셋": "1. Mean Dose / Etch Bias Offset",
        "CMP 단차 & Focus 산포": "2. CMP Dishing & Focus Scatter",
        "PR 코팅 편차 × 박막 Swing 간섭": "3. PR Radial Coat x Optical Swing",
        "PEB 핫플레이트 온도 구배": "4. PEB Hotplate Thermal Gradient",
        "스캐너 샷 Dose 노이즈": "5. Scanner Shot Dose Noise",
    }
    labels = [short_map.get(str(r["cause"]), str(r["cause"])) for r in rows]
    rms_vals = [float(r["rms_error_nm"]) for r in rows]
    shares = [float(r["variance_share_pct"]) for r in rows]

    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    colors = ["#d62728" if s >= 30.0 else ("#ff7f0e" if s >= 10.0 else "#1f77b4") for s in shares]
    bars = ax.barh(labels, rms_vals, color=colors, alpha=0.88)
    for b, sh in zip(bars, shares):
        w = b.get_width()
        ax.text(w + 0.08, b.get_y() + b.get_height() / 2, f"{w:.2f} nm ({sh:.1f}%)", va="center", fontsize=8.5)
    ax.set_xlim(0, max(rms_vals + [1.0]) * 1.28)
    ax.set_title(f"Cycle {cycle.cycle_id} Root-Cause CD Error Decomposition (RMS nm & Share %)")
    ax.set_xlabel("Isolated RMS Error Contribution (nm)")
    ax.grid(True, axis="x", linestyle=":", alpha=0.5)
    fig.tight_layout()
    return fig
