"""Stage 6: CD prediction models (Linear, Random Forest, XGBoost), SHAP analysis & Extrapolation Proof.

Explicitly distinguishes statistical surrogate modeling from physical causality:
1. Evaluates LR / RF / XGBoost on noisy physics-based synthetic Fab data.
2. Uses SHAP values on XGBoost to decompose CD variation into physical root-cause drivers.
3. Demonstrates out-of-range extrapolation failure (trained on 193 nm, tested on 248 nm)
   to prove why ML cannot replace underlying photolithography physics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
import shap
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

from src.data.generator import generate_synthetic_fab_dataset

ML_NUMERIC_FEATURES: Tuple[str, ...] = (
    "wavelength_nm",
    "na",
    "exposure_dose_mj_cm2",
    "focus_nm",
    "abs_focus_nm",
    "pr_thickness_nm",
    "barc_thickness_nm",
    "peb_temp_c",
    "soft_bake_temp_c",
    "dev_time_s",
    "dev_conc_wt_pct",
    "hmds_score",
    "reflectance",
    "eta_abs",
)
ML_CATEGORICAL_FEATURES: Tuple[str, ...] = ("underlayer", "illumination", "pattern")


@dataclass(frozen=True)
class ModelBenchmarkResult:
    """Trained models, evaluation metrics, test predictions, and SHAP root-cause importance."""

    metrics_df: pd.DataFrame
    best_model_name: str
    models: Dict[str, Pipeline]
    y_test: np.ndarray
    predictions: Dict[str, np.ndarray]
    importance_df: pd.DataFrame
    shap_method: str
    feature_names: Tuple[str, ...]


@dataclass(frozen=True)
class ExtrapolationExperimentResult:
    """Out-of-distribution test proving ML tree models fail outside training physics domain."""

    train_domain: str
    test_domain: str
    summary_df: pd.DataFrame
    y_true: np.ndarray
    predictions: Dict[str, np.ndarray]


def _add_physics_features(df: pd.DataFrame) -> pd.DataFrame:
    """Physics-informed feature engineering using only recipe inputs (zero TMM leakage).

    Adds quadratic defocus (Bossung symmetry) and thin-film interference phase harmonics
    cos/sin(4*pi*n*d/lambda) for PR and BARC thickness so tree/linear models capture swing curves.
    """
    out = df.copy()
    wl = np.maximum(out["wavelength_nm"].to_numpy(dtype=float), 1.0)
    d_pr = out["pr_thickness_nm"].to_numpy(dtype=float)
    d_barc = out["barc_thickness_nm"].to_numpy(dtype=float)
    phi_pr = 4.0 * np.pi * 1.70 * d_pr / wl
    phi_barc = 4.0 * np.pi * 1.75 * d_barc / wl
    out["focus_sq"] = out["focus_nm"].to_numpy(dtype=float) ** 2
    na_arr = out["na"].to_numpy(dtype=float)
    out["defocus_optical_u2"] = (out["focus_nm"].to_numpy(dtype=float) * (na_arr**2) / wl) ** 2
    out["pr_phase_cos"] = np.cos(phi_pr)
    out["pr_phase_sin"] = np.sin(phi_pr)
    out["barc_phase_cos"] = np.cos(phi_barc)
    out["barc_phase_sin"] = np.sin(phi_barc)
    out["log_dose"] = np.log(np.maximum(out["exposure_dose_mj_cm2"].to_numpy(dtype=float), 1e-3))
    return out


ENGINEERED_FEATURES: Tuple[str, ...] = (
    "focus_sq",
    "defocus_optical_u2",
    "pr_phase_cos",
    "pr_phase_sin",
    "barc_phase_cos",
    "barc_phase_sin",
    "log_dose",
)


def _build_preprocessor(
    num_cols: Sequence[str], cat_cols: Sequence[str]
) -> Pipeline:
    all_num = list(num_cols) + list(ENGINEERED_FEATURES)
    return Pipeline(
        steps=[
            ("phys_fe", FunctionTransformer(_add_physics_features, validate=False)),
            (
                "col_tf",
                ColumnTransformer(
                    transformers=[
                        ("num", StandardScaler(), all_num),
                        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), list(cat_cols)),
                    ]
                ),
            ),
        ]
    )


def _compute_shap_importance(
    xgb_pipeline: Pipeline,
    x_train: pd.DataFrame,
    x_test: pd.DataFrame,
    y_test: pd.Series,
) -> Tuple[pd.DataFrame, str]:
    """Compute mean |SHAP| feature importance on XGBoost, with safe fallback if TreeExplainer mismatches."""
    pre = xgb_pipeline.named_steps["pre"]
    reg = xgb_pipeline.named_steps["model"]
    x_test_trans = pre.transform(x_test)
    feat_names = list(pre.named_steps["col_tf"].get_feature_names_out())
    clean_names = [f.split("__", 1)[-1] for f in feat_names]

    try:
        explainer = shap.TreeExplainer(reg)
        shap_vals = explainer.shap_values(x_test_trans)
        mean_abs = np.mean(np.abs(shap_vals), axis=0)
        method = "SHAP TreeExplainer (mean |SHAP| nm)"
    except Exception:
        try:
            bg = pre.transform(x_train.iloc[: min(60, len(x_train))])
            explainer = shap.Explainer(reg.predict, bg)
            shap_vals = explainer(x_test_trans[: min(80, len(x_test_trans))]).values
            mean_abs = np.mean(np.abs(shap_vals), axis=0)
            method = "SHAP Permutation/Model-Agnostic (mean |SHAP| nm)"
        except Exception:
            perm = permutation_importance(
                xgb_pipeline, x_test, y_test, n_repeats=5, random_state=42, scoring="neg_root_mean_squared_error"
            )
            df_imp = (
                pd.DataFrame({"feature": list(x_test.columns), "importance": perm.importances_mean})
                .sort_values("importance", ascending=False)
                .reset_index(drop=True)
            )
            return df_imp, "Permutation Importance (RMSE increase nm)"

    df_imp = (
        pd.DataFrame({"feature": clean_names, "importance": mean_abs})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )
    return df_imp, method


def train_and_evaluate_cd_models(
    df: pd.DataFrame,
    target_col: str = "cd_measured_nm",
    numeric_features: Sequence[str] = ML_NUMERIC_FEATURES,
    categorical_features: Sequence[str] = ML_CATEGORICAL_FEATURES,
    test_size: float = 0.20,
    cv_folds: int = 5,
    random_state: int = 42,
) -> ModelBenchmarkResult:
    """Train and benchmark Linear Regression, Random Forest, and XGBoost for CD prediction."""
    num_cols = [c for c in numeric_features if c in df.columns]
    cat_cols = [c for c in categorical_features if c in df.columns]
    used_cols = num_cols + cat_cols

    x = df[used_cols].copy()
    y = df[target_col].astype(float).copy()

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=test_size, random_state=random_state
    )

    estimators: Dict[str, Any] = {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(
            n_estimators=160, max_depth=14, min_samples_leaf=2, random_state=random_state, n_jobs=-1
        ),
        "XGBoost": XGBRegressor(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.07,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=random_state,
            n_jobs=1,
            verbosity=0,
        ),
    }

    kf = KFold(n_splits=cv_folds, shuffle=True, random_state=random_state)
    trained_models: Dict[str, Pipeline] = {}
    preds: Dict[str, np.ndarray] = {}
    metric_rows: List[Dict[str, object]] = []

    for name, est in estimators.items():
        pipe = Pipeline([("pre", _build_preprocessor(num_cols, cat_cols)), ("model", est)])
        cv_scores = cross_val_score(
            pipe, x_train, y_train, cv=kf, scoring="neg_root_mean_squared_error", n_jobs=1
        )
        pipe.fit(x_train, y_train)
        y_pred = pipe.predict(x_test)

        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        mae = float(mean_absolute_error(y_test, y_pred))
        r2 = float(r2_score(y_test, y_pred))
        cv_rmse = float(-np.mean(cv_scores))

        trained_models[name] = pipe
        preds[name] = y_pred
        metric_rows.append(
            {
                "Model": name,
                "R2": r2,
                "RMSE (nm)": rmse,
                "MAE (nm)": mae,
                "CV RMSE (nm)": cv_rmse,
            }
        )

    metrics_df = pd.DataFrame(metric_rows).sort_values("RMSE (nm)").reset_index(drop=True)
    best_model_name = str(metrics_df.iloc[0]["Model"])
    importance_df, shap_method = _compute_shap_importance(
        trained_models["XGBoost"], x_train, x_test, y_test
    )

    return ModelBenchmarkResult(
        metrics_df=metrics_df,
        best_model_name=best_model_name,
        models=trained_models,
        y_test=y_test.to_numpy(),
        predictions=preds,
        importance_df=importance_df,
        shap_method=shap_method,
        feature_names=tuple(used_cols),
    )


def run_extrapolation_experiment(
    n_train: int = 360,
    n_test: int = 120,
    seed: int = 42,
) -> ExtrapolationExperimentResult:
    """Train ML models ONLY on 193 nm (ArF Dry + ArFi) and evaluate on unseen 248 nm (KrF).

    Demonstrates that data-driven ML fails catastrophically on out-of-domain wavelengths/CD regimes,
    whereas the physics engine remains exact up to measurement noise.
    """
    train_df = generate_synthetic_fab_dataset(
        n_samples=n_train,
        nodes=("ArF_Dry_193", "ArFi_193"),
        seed=seed,
    )
    test_df = generate_synthetic_fab_dataset(
        n_samples=n_test,
        nodes=("KrF_248",),
        seed=seed + 101,
    )

    num_cols = list(ML_NUMERIC_FEATURES)
    cat_cols = list(ML_CATEGORICAL_FEATURES)
    used_cols = num_cols + cat_cols

    x_train, y_train = train_df[used_cols], train_df["cd_measured_nm"].to_numpy()
    x_test, y_test = test_df[used_cols], test_df["cd_measured_nm"].to_numpy()

    preds: Dict[str, np.ndarray] = {
        "Physics Model (TMM+Bossung)": test_df["cd_ideal_nm"].to_numpy(),
    }

    ml_specs = {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(n_estimators=120, max_depth=12, random_state=seed, n_jobs=-1),
        "XGBoost": XGBRegressor(n_estimators=150, max_depth=5, learning_rate=0.07, random_state=seed, n_jobs=1, verbosity=0),
    }
    for name, est in ml_specs.items():
        pipe = Pipeline([("pre", _build_preprocessor(num_cols, cat_cols)), ("model", est)])
        pipe.fit(x_train, y_train)
        preds[name] = pipe.predict(x_test)

    rows = []
    for name, y_hat in preds.items():
        rows.append(
            {
                "Model": name,
                "Test RMSE (nm)": float(np.sqrt(mean_squared_error(y_test, y_hat))),
                "Test MAE (nm)": float(mean_absolute_error(y_test, y_hat)),
                "Mean Bias (nm)": float(np.mean(y_hat - y_test)),
            }
        )
    summary_df = pd.DataFrame(rows).sort_values("Test RMSE (nm)").reset_index(drop=True)
    return ExtrapolationExperimentResult(
        train_domain="193 nm (ArF Dry + ArFi)",
        test_domain="248 nm (KrF — Unseen Wavelength)",
        summary_df=summary_df,
        y_true=y_test,
        predictions=preds,
    )
