"""Stage 5 & 6 Matplotlib visualizations: 300mm Wafer CDU Map, Correlation, DOE, ML & Extrapolation."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.patches import Circle

from src.ml.models import ExtrapolationExperimentResult, ModelBenchmarkResult
from src.physics.process_models import WaferCDUResult


def plot_wafer_cdu_map(cdu: WaferCDUResult) -> Figure:
    """Plot 300 mm wafer 2D CD uniformity heatmap and CD distribution histogram."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.0, 4.6))

    wafer_circle = Circle((0, 0), 150.0, fill=False, edgecolor="black", linewidth=1.8)
    ax1.add_patch(wafer_circle)
    sc = ax1.scatter(cdu.x_mm, cdu.y_mm, c=cdu.cd_nm, cmap="coolwarm", s=68, marker="s", edgecolors="none")
    fig.colorbar(sc, ax=ax1, label="Measured CD (nm)")
    ax1.set_xlim(-160, 160)
    ax1.set_ylim(-160, 160)
    ax1.set_aspect("equal")
    ax1.set_title(
        f"300 mm Wafer CDU Map ({cdu.node_key})\n"
        f"Mean={cdu.mean_cd_nm:.2f} nm | 3σ={cdu.cdu_3sigma_nm:.2f} nm ({cdu.cdu_3sigma_pct:.2f}%)"
    )
    ax1.set_xlabel("Wafer X (mm)")
    ax1.set_ylabel("Wafer Y (mm)")
    ax1.grid(True, linestyle=":", alpha=0.35)

    ax2.hist(cdu.cd_nm, bins=22, color="#1f77b4", alpha=0.82, edgecolor="white")
    ax2.axvline(cdu.target_cd_nm, color="black", linestyle="-", linewidth=1.6, label=f"Target {cdu.target_cd_nm:.1f} nm")
    ax2.axvline(cdu.target_cd_nm * 0.9, color="#d62728", linestyle="--", linewidth=1.3, label="±10% Spec")
    ax2.axvline(cdu.target_cd_nm * 1.1, color="#d62728", linestyle="--", linewidth=1.3)
    ax2.set_title(f"Wafer CD Distribution (Yield = {cdu.within_spec_yield_pct:.1f}%)")
    ax2.set_xlabel("CD (nm)")
    ax2.set_ylabel("Site Count")
    ax2.grid(True, linestyle=":", alpha=0.4)
    ax2.legend(frameon=True)

    fig.tight_layout()
    return fig


def plot_correlation_heatmap(corr_df: pd.DataFrame) -> Figure:
    """Plot Pearson correlation matrix heatmap across process parameters and CD."""
    fig, ax = plt.subplots(figsize=(8.4, 6.8))
    mat = corr_df.to_numpy()
    im = ax.imshow(mat, cmap="RdBu_r", vmin=-1.0, vmax=1.0)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Pearson r")

    labels = list(corr_df.columns)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8.5)
    ax.set_yticklabels(labels, fontsize=8.5)

    for i in range(len(labels)):
        for j in range(len(labels)):
            val = mat[i, j]
            txt_color = "white" if abs(val) > 0.55 else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", color=txt_color, fontsize=7.0)

    ax.set_title("Process Parameter Correlation Matrix (Synthetic Fab Data)")
    fig.tight_layout()
    return fig


def plot_doe_effects(effects_df: pd.DataFrame) -> Figure:
    """Plot Pareto bar chart of 2^4 Factorial DOE Main & Interaction Effects on CD."""
    top = effects_df.head(10).iloc[::-1]
    colors = ["#1f77b4" if t == "Main" else "#ff7f0e" for t in top["type"]]

    fig, ax = plt.subplots(figsize=(7.8, 4.5))
    ax.barh(top["term"], top["effect_nm"], color=colors, alpha=0.9)
    ax.axvline(0.0, color="black", linewidth=1.0)
    ax.set_title("2^4 Full Factorial DOE: Main & 2-Way Interaction Effects on CD")
    ax.set_xlabel("Signed CD Effect (High - Low, nm)")
    ax.grid(True, axis="x", linestyle=":", alpha=0.5)
    fig.tight_layout()
    return fig


def plot_ml_benchmark_and_shap(bench: ModelBenchmarkResult) -> Figure:
    """Plot Actual vs Predicted CD for best model and top SHAP feature importances."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.6))

    y_true = bench.y_test
    y_pred = bench.predictions[bench.best_model_name]
    lo = min(float(np.min(y_true)), float(np.min(y_pred)))
    hi = max(float(np.max(y_true)), float(np.max(y_pred)))

    ax1.scatter(y_true, y_pred, alpha=0.65, s=26, color="#1f77b4", edgecolors="none")
    ax1.plot([lo, hi], [lo, hi], color="#d62728", linestyle="--", linewidth=1.8, label="Ideal y = x")
    best_row = bench.metrics_df[bench.metrics_df["Model"] == bench.best_model_name].iloc[0]
    ax1.set_title(
        f"Actual vs. Predicted CD ({bench.best_model_name})\n"
        f"R²={best_row['R2']:.4f} | RMSE={best_row['RMSE (nm)']:.2f} nm"
    )
    ax1.set_xlabel("Measured Synthetic CD (nm)")
    ax1.set_ylabel("Predicted CD (nm)")
    ax1.grid(True, linestyle=":", alpha=0.45)
    ax1.legend(frameon=True)

    top_imp = bench.importance_df.head(10).iloc[::-1]
    ax2.barh(top_imp["feature"], top_imp["importance"], color="#2ca02c", alpha=0.88)
    ax2.set_title(f"Root-Cause Feature Importance\n({bench.shap_method})")
    ax2.set_xlabel("Importance (nm)")
    ax2.grid(True, axis="x", linestyle=":", alpha=0.45)

    fig.tight_layout()
    return fig


def plot_extrapolation_proof(extrap: ExtrapolationExperimentResult) -> Figure:
    """Visualize out-of-domain failure of ML vs exactness of Physics Model."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.6))

    # Panel 1: RMSE bar chart
    df = extrap.summary_df
    colors = ["#2ca02c" if "Physics" in m else "#d62728" for m in df["Model"]]
    ax1.barh(df["Model"], df["Test RMSE (nm)"], color=colors, alpha=0.88)
    ax1.set_title(f"Out-of-Domain Extrapolation Error\nTrain: {extrap.train_domain} → Test: {extrap.test_domain}")
    ax1.set_xlabel("Test RMSE on Unseen 248 nm KrF (nm)")
    ax1.grid(True, axis="x", linestyle=":", alpha=0.45)

    # Panel 2: Actual vs Predicted scatter comparing Physics vs XGBoost on unseen 248 nm
    y_true = extrap.y_true
    ax2.scatter(y_true, extrap.predictions["Physics Model (TMM+Bossung)"], s=24, alpha=0.75, color="#2ca02c", label="Physics Model")
    ax2.scatter(y_true, extrap.predictions["XGBoost"], s=24, alpha=0.75, color="#d62728", label="XGBoost (Trained on 193 nm Only)")
    lo, hi = float(np.min(y_true)), float(np.max(y_true))
    ax2.plot([lo, hi], [lo, hi], color="black", linestyle="--", linewidth=1.4, label="Ideal y = x")
    ax2.set_title("Why ML Cannot Replace Physical Causality")
    ax2.set_xlabel("Actual 248 nm KrF CD (nm)")
    ax2.set_ylabel("Predicted CD (nm)")
    ax2.grid(True, linestyle=":", alpha=0.45)
    ax2.legend(frameon=True, fontsize=8.5)

    fig.tight_layout()
    return fig
