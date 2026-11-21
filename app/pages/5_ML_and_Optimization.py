"""Page 5: ML CD Prediction (LR/RF/XGB), SHAP Root-Cause, Recipe Optimizer & Extrapolation Proof."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.glossary import render_analogy_cards, render_glossary_toolbar, render_page_concept_guide, tip
from src.data.generator import generate_synthetic_fab_dataset
from src.ml.models import run_extrapolation_experiment, train_and_evaluate_cd_models
from src.ml.optimizer import optimize_process_conditions
from src.physics.constants import EXPOSURE_NODES, ILLUMINATION_PRESETS, PATTERN_PRESETS
from src.physics.exposure_fem import bossung_cd
from src.physics.optics_tmm import build_litho_stack, get_ambient_for_node, simulate_multilayer_optics
from src.physics.process_models import tier2_process_shift
from src.physics.resolution import depth_of_focus
from src.visualization.data_ml_plots import (
    plot_extrapolation_proof,
    plot_ml_benchmark_and_shap,
)

st.set_page_config(page_title="ML & Optimization", page_icon="🤖", layout="wide")

DUV_NODES = [k for k, v in EXPOSURE_NODES.items() if not v.comparison_only]
PAGE5_TERMS = ("ml_models", "SHAP", "optimizer", "extrapolation", "eta_abs", "PW", "BARC")

with st.sidebar:
    st.header("ML 학습 및 최적화 설정")
    node_key = st.selectbox("대상 DUV 노광 세대", DUV_NODES, index=2, help=tip("wavelength"))
    n_samples = st.slider("학습용 가상 Fab 샘플 수", 300, 1000, 550, 50, help=tip("LHS"))
    opt_underlayer = st.selectbox("최적화 대상 하부막", ["Bare_Si", "SiO2", "PolySi", "Al_Metal"], index=3, help=tip("underlayer"))
    opt_illum = st.selectbox("최적화 조명계", list(ILLUMINATION_PRESETS.keys()), index=1, help=tip("OAI"))
    opt_pattern = st.selectbox("최적화 패턴", list(PATTERN_PRESETS.keys()), index=0, help=tip("pattern"))

render_glossary_toolbar("page5", PAGE5_TERMS)

st.title("5️⃣ 머신러닝 CD 예측 · SHAP 원인 분석 · 최적 공정조건 탐색")
st.caption("Linear / Random Forest / XGBoost 성능 비교, 물리 검증 역최적화, 그리고 ML의 외삽 한계(물리 인과 불가) 증명")

render_page_concept_guide(
    "page5",
    "이 페이지 핵심 용어 & AI/물리 결합 원리 쉽게 보기 (XGBoost, SHAP, Surrogate 최적화, 외삽 한계)",
    PAGE5_TERMS,
    quick_summary=(
        "- **왜 물리 공식을 알면서 ML을 쓰나?**: 실제 Fab엔 노이즈가 섞여 있고 다차원 조건 탐색이 느려. ML은 **빠른 대리모델(Surrogate)**과 **SHAP 기반 산포 원인 진단**에 강력해.\n"
        "- **하이브리드 피처**: 원시 레시피만 넣으면 박막 간섭 진동 때문에 오차가 커서, 인라인 광학 계측(`reflectance`, `eta_abs`)과 간섭 위상 항($\\cos/\\sin$)을 함께 넣었어.\n"
        "- **4번째 탭(외삽 실패 증명)**: 193nm로만 배운 AI에게 248nm를 물으면 완전히 틀리는 걸 보여줘서, **'AI는 물리 원리를 대체하는 게 아니라 보조하는 도구'**라는 핵심 통찰을 증명해."
    ),
)


@st.cache_resource(show_spinner="ML 모델 학습 및 SHAP 계산 중...")
def _train_cached(n_key: str, n: int):
    df = generate_synthetic_fab_dataset(n_samples=n, nodes=(n_key,), seed=42)
    return train_and_evaluate_cd_models(df, cv_folds=5, random_state=42)


@st.cache_data(show_spinner="외삽 한계 실험(193nm 학습 → 248nm 평가) 실행 중...")
def _extrap_cached():
    return run_extrapolation_experiment(n_train=360, n_test=120, seed=42)


bench = _train_cached(node_key, n_samples)

with st.expander("🎨 그림과 비유로 이해하기 (오답노트 AI · 팀플 정산 SHAP · 외삽 한계)", icon=":material/palette:", expanded=False):
    render_analogy_cards(
        [
            ("🌳 Linear vs RF vs XGBoost", "Linear는 직선 자로 긋기, RF는 여러 나무의 다수결, XGBoost는 앞 나무가 틀린 오차를 집중 보완하는 '오답노트 앙상블'이야.", "비선형 박막 간섭에서 XGBoost가 우수"),
            ("🧾 SHAP = 팀플 기여도 정산표", "최종 CD가 목표에서 왜 ±몇 nm 벗어났는지, 각 공정 변수의 책임량을 공평하게(Shapley Value) 분해해 줘.", "가장 긴 막대가 1순위 개선 타겟"),
            ("🚧 외삽 실패 = 문제집 암기 학생", "193nm 데이터만 외운 AI에게 처음 보는 248nm를 물으면 엉뚱한 답을 찍어. AI는 물리 검증과 함께 써야 안전해.", "Tab 4에서 물리 vs XGBoost 비교"),
        ]
    )
    st.mermaid_chart(
        """
        flowchart LR
            A["1,200개 후보 레시피"] --> B["XGBoost Surrogate<br/>(0.05초 고속 스크리닝)"]
            B --> C["상위 8개 유망 후보"]
            C --> D["물리 엔진 검증 (TMM + FEM)<br/>PW Area 최대 & 결함 최소 선정"]
            D --> E["최종 안전 레시피 확정"]
        """,
        alt="ML 대리모델 고속 스크리닝과 물리 엔진 최종 검증 하이브리드 최적화 흐름도",
    )

tab1, tab2, tab3, tab4 = st.tabs([
    "모델 성능 & SHAP 원인 분석",
    "실시간 CD 예측기 (물리 vs ML)",
    "최적 공정조건 탐색 (PW 극대화)",
    "ML의 물리적 한계 (외삽 실패 증명)",
])

with tab1:
    st.dataframe(bench.metrics_df, width="stretch", hide_index=True)
    fig_ml = plot_ml_benchmark_and_shap(bench)
    st.pyplot(fig_ml)
    plt.close(fig_ml)

with tab2:
    node = EXPOSURE_NODES[node_key]
    p1, p2, p3 = st.columns(3)
    with p1:
        dose_in = st.slider("Dose (mJ/cm²)", 15.0, 45.0, float(node.nominal_dose_mj_cm2), 0.5, help=tip("exposure_dose"))
        focus_in = st.slider("Focus (nm)", -140.0, 140.0, 0.0, 5.0, help=tip("DOF"))
        na_in = st.slider("NA", float(node.na_min), float(node.na_max), float(node.na_default), 0.01, help=tip("NA"))
    with p2:
        pr_in = st.slider("PR Thickness (nm)", 70.0, 400.0, float(node.default_pr_thickness_nm), 2.0, help=tip("swing_curve"))
        barc_in = st.slider("BARC Thickness (nm)", 0.0, 100.0, 28.0, 1.0, help=tip("BARC"))
        peb_in = st.slider("PEB Temp (°C)", 108.0, 122.0, 115.0, 0.5, help=tip("arrhenius"))
    with p3:
        sb_in = st.slider("Soft Bake Temp (°C)", 95.0, 120.0, 105.0, 1.0, help=tip("bake"))
        dev_in = st.slider("Dev Time (s)", 40.0, 80.0, 60.0, 1.0, help=tip("mack"))
        conc_in = st.slider("Dev Conc (wt%)", 2.28, 2.48, 2.38, 0.01, help=tip("mack"))

    # Exact physics baseline (also provides inline optical metrology features for hybrid ML)
    st_one = build_litho_stack(node.wavelength_nm, get_ambient_for_node(node_key), pr_in, barc_in, opt_underlayer)
    opt_one = simulate_multilayer_optics(st_one, node.wavelength_nm, n_z_points=60)
    dof_one = float(depth_of_focus(node.wavelength_nm, na_in, node.k2_default, node.n_fluid, opt_illum, opt_pattern))
    t2_one = tier2_process_shift(sb_in, 60.0, peb_in, 60.0, 125.0, dev_in, conc_in, 23.0, node.default_target_cd_nm)
    phys_cd = float(bossung_cd(dose_in, focus_in, node.default_target_cd_nm, node.nominal_dose_mj_cm2, dof_one, opt_one.effective_dose_factor, opt_pattern, opt_illum, 0.0, t2_one["process_cd_bias_nm"], t2_one["contrast_modifier"]))

    x_one = pd.DataFrame([{
        "wavelength_nm": node.wavelength_nm,
        "na": na_in,
        "exposure_dose_mj_cm2": dose_in,
        "focus_nm": focus_in,
        "abs_focus_nm": abs(focus_in),
        "pr_thickness_nm": pr_in,
        "barc_thickness_nm": barc_in,
        "peb_temp_c": peb_in,
        "soft_bake_temp_c": sb_in,
        "dev_time_s": dev_in,
        "dev_conc_wt_pct": conc_in,
        "hmds_score": 1.0,
        "reflectance": opt_one.reflectance,
        "eta_abs": opt_one.effective_dose_factor,
        "underlayer": opt_underlayer,
        "illumination": opt_illum,
        "pattern": opt_pattern,
    }])
    xgb_cd = float(bench.models["XGBoost"].predict(x_one)[0])
    rf_cd = float(bench.models["Random Forest"].predict(x_one)[0])
    lr_cd = float(bench.models["Linear Regression"].predict(x_one)[0])

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("물리 모델 CD (기준)", f"{phys_cd:.2f} nm", help="TMM 박막 간섭 + Bossung + Tier 2 물리 방정식으로 직접 계산한 정답 기준값입니다.")
    r2.metric("XGBoost 예측 CD", f"{xgb_cd:.2f} nm", delta=f"{xgb_cd - phys_cd:+.2f} nm", help=tip("ml_models"))
    r3.metric("Random Forest 예측 CD", f"{rf_cd:.2f} nm", delta=f"{rf_cd - phys_cd:+.2f} nm", help=tip("ml_models"))
    r4.metric("Linear Reg 예측 CD", f"{lr_cd:.2f} nm", delta=f"{lr_cd - phys_cd:+.2f} nm", help=tip("ml_models"))

with tab3:
    target_opt_cd = st.number_input("최적화 목표 CD (nm)", 25.0, 250.0, float(EXPOSURE_NODES[node_key].default_target_cd_nm), 1.0, help=tip("CD"))
    if st.button("최적 공정조건 탐색 실행 (ML 스크리닝 + 물리 FEM 최종 검증)", type="primary", help=tip("optimizer")):
        with st.spinner("후보 레시피 스크리닝 및 FEM Process Window 검증 중..."):
            opt_res = optimize_process_conditions(
                node_key=node_key,
                target_cd_nm=target_opt_cd,
                underlayer=opt_underlayer,
                illumination=opt_illum,
                pattern=opt_pattern,
                surrogate_model=bench.models["XGBoost"],
            )
        st.success(opt_res.rationale)
        st.dataframe(opt_res.candidates_df, width="stretch", hide_index=True)

with tab4:
    st.warning(
        "머신러닝은 학습 데이터 영역 내부의 고속 근사·최적화·산포 진단에는 강력하지만, "
        "**물리적 인과관계를 이해하지 못하므로 학습 범위 밖(예: 193 nm 학습 → 248 nm KrF 외삽)에서는 예측이 붕괴**합니다.",
        title="핵심 엔지니어링 통찰 (외삽 한계)",
    )
    extrap = _extrap_cached()
    st.dataframe(extrap.summary_df, width="stretch", hide_index=True)
    fig_ex = plot_extrapolation_proof(extrap)
    st.pyplot(fig_ex)
    plt.close(fig_ex)
