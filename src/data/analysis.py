"""Stage 5: Statistical process data analysis (Correlation, Standardized OLS Regression, 2^k DOE)."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from src.physics.constants import EXPOSURE_NODES
from src.physics.exposure_fem import bossung_cd
from src.physics.optics_tmm import build_litho_stack, get_ambient_for_node, simulate_multilayer_optics
from src.physics.process_models import tier2_process_shift
from src.physics.resolution import depth_of_focus

DEFAULT_ANALYSIS_FEATURES: Tuple[str, ...] = (
    "exposure_dose_mj_cm2",
    "focus_nm",
    "abs_focus_nm",
    "pr_thickness_nm",
    "barc_thickness_nm",
    "peb_temp_c",
    "soft_bake_temp_c",
    "dev_time_s",
    "dev_conc_wt_pct",
    "na",
    "eta_abs",
    "substrate_reflectance",
)


@dataclass(frozen=True)
class OLSRegressionReport:
    """Multiple linear regression summary with standardized beta weights and p-values."""

    target: str
    r2: float
    adj_r2: float
    rmse: float
    n_samples: int
    coefficients_df: pd.DataFrame


def compute_correlation_matrix(
    df: pd.DataFrame,
    features: Sequence[str] = DEFAULT_ANALYSIS_FEATURES,
    target: str = "cd_measured_nm",
) -> pd.DataFrame:
    """Compute Pearson correlation matrix across selected numeric features and target."""
    cols = [c for c in list(features) + [target] if c in df.columns]
    # Drop zero-variance columns to avoid NaN rows in correlation heatmap
    valid_cols = [c for c in cols if df[c].nunique(dropna=True) > 1]
    return df[valid_cols].corr(method="pearson")


def run_ols_regression(
    df: pd.DataFrame,
    features: Sequence[str] = (
        "exposure_dose_mj_cm2",
        "abs_focus_nm",
        "pr_thickness_nm",
        "barc_thickness_nm",
        "peb_temp_c",
        "soft_bake_temp_c",
        "dev_time_s",
        "dev_conc_wt_pct",
        "eta_abs",
    ),
    target: str = "cd_measured_nm",
) -> OLSRegressionReport:
    """Fit OLS multiple regression via normal equations with standardized betas and t-test p-values."""
    valid_feats = [f for f in features if f in df.columns and df[f].nunique(dropna=True) > 1]
    if not valid_feats:
        raise ValueError("No valid non-constant features available for OLS regression")

    x_raw = df[valid_feats].to_numpy(dtype=float)
    y = df[target].to_numpy(dtype=float)
    n, p = x_raw.shape
    if n <= p + 1:
        raise ValueError(f"Insufficient samples ({n}) for {p} predictors")

    x_design = np.column_stack([np.ones(n), x_raw])
    beta, _, _, _ = np.linalg.lstsq(x_design, y, rcond=None)
    y_hat = x_design @ beta
    resid = y - y_hat

    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / max(ss_tot, 1e-12)
    adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / max(n - p - 1, 1)
    rmse = float(np.sqrt(ss_res / n))

    # Standard errors and two-sided t-test p-values
    dof = n - p - 1
    mse = ss_res / max(dof, 1)
    xtx_inv = np.linalg.pinv(x_design.T @ x_design)
    se = np.sqrt(np.maximum(np.diag(mse * xtx_inv), 1e-18))
    t_stats = beta / se
    p_vals = 2.0 * (1.0 - stats.t.cdf(np.abs(t_stats), df=dof))

    # Standardized coefficients (effect in std(y) per 1 std(x))
    y_std = float(np.std(y, ddof=1))
    x_stds = np.std(x_raw, axis=0, ddof=1)
    std_betas = [np.nan] + [float(beta[j + 1] * x_stds[j] / max(y_std, 1e-12)) for j in range(p)]

    coef_df = pd.DataFrame(
        {
            "feature": ["intercept", *valid_feats],
            "coef": beta,
            "std_beta": std_betas,
            "abs_std_beta": [np.nan] + [abs(b) for b in std_betas[1:]],
            "t_stat": t_stats,
            "p_value": p_vals,
        }
    )
    return OLSRegressionReport(
        target=target,
        r2=float(r2),
        adj_r2=float(adj_r2),
        rmse=rmse,
        n_samples=n,
        coefficients_df=coef_df,
    )


def run_2level_factorial_doe(
    node_key: str = "ArFi_193",
    underlayer: str = "Al_Metal",
    illumination: str = "Annular",
    pattern: str = "Dense_1to1",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Run a 2^4 full factorial DOE (Dose, Focus, BARC, PEB Temp) to quantify main & interaction effects."""
    node = EXPOSURE_NODES[node_key]
    ambient = get_ambient_for_node(node_key)
    dof_hi = float(
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

    factors: Dict[str, Tuple[float, float]] = {
        "Dose": (node.nominal_dose_mj_cm2 * 0.88, node.nominal_dose_mj_cm2 * 1.12),
        "AbsFocus": (0.0, 90.0),
        "BARC": (0.0, 28.0),
        "PEB_Temp": (112.0, 118.0),
    }
    factor_names = list(factors.keys())

    runs: List[Dict[str, float]] = []
    for levels in product([-1, +1], repeat=len(factor_names)):
        coded = dict(zip(factor_names, levels))
        dose_val = factors["Dose"][0 if coded["Dose"] == -1 else 1]
        focus_val = factors["AbsFocus"][0 if coded["AbsFocus"] == -1 else 1]
        barc_val = factors["BARC"][0 if coded["BARC"] == -1 else 1]
        peb_val = factors["PEB_Temp"][0 if coded["PEB_Temp"] == -1 else 1]

        stack = build_litho_stack(
            wavelength_nm=node.wavelength_nm,
            ambient_material=ambient,
            pr_thickness_nm=node.default_pr_thickness_nm,
            barc_thickness_nm=barc_val,
            underlayer_material=underlayer,
            underlayer_thickness_nm=100.0,
        )
        optics = simulate_multilayer_optics(stack, node.wavelength_nm, n_z_points=60)
        t2 = tier2_process_shift(peb_temp_c=peb_val, target_cd_nm=node.default_target_cd_nm)
        cd_val = float(
            bossung_cd(
                dose_val,
                focus_val,
                target_cd_nm=node.default_target_cd_nm,
                nominal_dose_mj_cm2=node.nominal_dose_mj_cm2,
                dof_scale_nm=dof_hi,
                effective_dose_factor=optics.effective_dose_factor,
                pattern=pattern,
                illumination=illumination,
                process_cd_bias_nm=t2["process_cd_bias_nm"],
                contrast_modifier=t2["contrast_modifier"],
            )
        )
        runs.append(
            {
                **coded,
                "dose_mj_cm2": dose_val,
                "focus_nm": focus_val,
                "barc_nm": barc_val,
                "peb_temp_c": peb_val,
                "eta_abs": optics.effective_dose_factor,
                "cd_nm": cd_val,
            }
        )

    runs_df = pd.DataFrame(runs)
    y = runs_df["cd_nm"].to_numpy()
    effects: List[Dict[str, object]] = []

    # Main effects
    for f in factor_names:
        c = runs_df[f].to_numpy()
        eff = float(np.mean(y[c == 1]) - np.mean(y[c == -1]))
        effects.append({"term": f, "type": "Main", "effect_nm": eff, "abs_effect_nm": abs(eff)})

    # 2-way interactions
    for i in range(len(factor_names)):
        for j in range(i + 1, len(factor_names)):
            f1, f2 = factor_names[i], factor_names[j]
            inter = runs_df[f1].to_numpy() * runs_df[f2].to_numpy()
            eff = float(np.mean(y[inter == 1]) - np.mean(y[inter == -1]))
            effects.append(
                {"term": f"{f1} × {f2}", "type": "Interaction", "effect_nm": eff, "abs_effect_nm": abs(eff)}
            )

    effects_df = pd.DataFrame(effects).sort_values("abs_effect_nm", ascending=False).reset_index(drop=True)
    return runs_df, effects_df
