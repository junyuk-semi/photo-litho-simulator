"""Page 4: 300mm Wafer CDU Map, Synthetic Fab Data Generator, Correlation, OLS & DOE."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.glossary import render_analogy_cards, render_glossary_toolbar, render_page_concept_guide, tip
from src.data.analysis import (
    compute_correlation_matrix,
    run_2level_factorial_doe,
    run_ols_regression,
)
from src.data.generator import generate_synthetic_fab_dataset
from src.physics.constants import EXPOSURE_NODES
from src.physics.process_models import simulate_wafer_cdu_map, spin_coating_thickness_nm
from src.visualization.data_ml_plots import (
    plot_correlation_heatmap,
    plot_doe_effects,
    plot_wafer_cdu_map,
)
from src.visualization.study_visuals import plot_cdu_radial_decomposition

st.set_page_config(page_title="Wafer CDU & Data Analysis", page_icon="📊", layout="wide")

DUV_NODES = [k for k, v in EXPOSURE_NODES.items() if not v.comparison_only]
PAGE4_TERMS = ("CDU", "spin_coating", "bake", "LHS", "correlation", "OLS", "DOE", "BARC")

with st.sidebar:
    st.header("웨이퍼 CDU & 데이터셋 설정")
    node_key = st.selectbox("DUV 노광 세대", DUV_NODES, index=2, help=tip("wavelength"))
    underlayer = st.selectbox("하부막", ["Bare_Si", "SiO2", "PolySi", "Al_Metal"], index=3, help=tip("underlayer"))
    barc_thick = st.slider("BARC 두께 (nm)", 0.0, 120.0, 28.0, 1.0, help=tip("BARC"))
    spin_rpm = st.slider("Spin Speed (RPM)", 1500.0, 6000.0, 3000.0, 100.0, help=tip("spin_coating"))
    viscosity = st.slider("PR Viscosity (cP)", 1.0, 20.0, 3.0, 0.5, help=tip("spin_coating"))
    pr_radial = st.slider("웨이퍼 반경 PR 두께 편차 (nm)", 0.5, 10.0, 3.5, 0.5, help=tip("CDU"))
    peb_radial = st.slider("PEB 핫플레이트 온도 편차 (°C)", 0.1, 2.5, 0.6, 0.1, help=tip("bake"))
    n_samples = st.slider("가상 Fab 데이터 샘플 수", 200, 1000, 500, 50, help=tip("LHS"))

render_glossary_toolbar("page4", PAGE4_TERMS)

st.title("4️⃣ 300mm 웨이퍼 CDU 맵 & 공정 데이터 분석 (DOE · 회귀)")
st.caption("가상 Fab 데이터(LHS DOE + 공정 산포) 기반 웨이퍼 균일도, 상관분석, 표준화 OLS 회귀 및 2⁴ 교호작용 분석")

render_page_concept_guide(
    "page4",
    "이 페이지 핵심 용어 & 통계 분석 읽는 법 (CDU 3σ, Meyerhofer, LHS, 상관계수, OLS, DOE)",
    PAGE4_TERMS,
    quick_summary=(
        "- **300mm 웨이퍼 CDU 맵**: 웨이퍼 중심과 가장자리의 PR 두께 차이 + PEB 온도 차이 때문에 칩 위치별로 CD가 달라지는 걸 시각화한 지도야. **3σ가 작을수록 균일한 우수 공정**이야.\n"
        "- **상관분석 & OLS**: 어떤 변수가 CD를 가장 크게 흔드는지 표준화 계수(`abs_std_beta`)로 순위를 매겨. 단, Focus처럼 좌우 대칭(포물선) 변수는 직선 상관계수 r이 작게 나올 수 있어.\n"
        "- **2⁴ 요인실험(DOE)**: Dose, Focus, BARC, PEB 4개 변수의 단일 효과(파란 막대)와 두 변수가 합쳐진 **교호작용(주황 막대)**을 정량 비교해."
    ),
)


@st.cache_data(show_spinner="가상 Fab 데이터 생성 중...")
def _cached_dataset(n_key: str, n: int):
    return generate_synthetic_fab_dataset(n_samples=n, nodes=(n_key,), seed=42)


tab1, tab2, tab3 = st.tabs(["300mm 웨이퍼 CDU 맵", "상관분석 & 다중회귀(OLS)", "2⁴ 요인실험(DOE) & 데이터"])

with tab1:
    est_pr = spin_coating_thickness_nm(spin_speed_rpm=spin_rpm, viscosity_cp=viscosity)
    st.info(f"Meyerhofer 스핀 코팅 추정 PR 두께: **{est_pr:.1f} nm** (Spin Speed={spin_rpm:.0f} RPM, Viscosity={viscosity:.1f} cP)")
    cdu = simulate_wafer_cdu_map(
        node_key=node_key,
        pr_thickness_nm=est_pr,
        barc_thickness_nm=barc_thick,
        underlayer_material=underlayer,
        pr_radial_range_nm=pr_radial,
        peb_radial_range_c=peb_radial,
    )
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("평균 CD", f"{cdu.mean_cd_nm:.2f} nm", help=tip("CD"))
    k2.metric("CD Uniformity (3σ)", f"{cdu.cdu_3sigma_nm:.2f} nm", help=tip("CDU"))
    k3.metric("CDU 3σ (%)", f"{cdu.cdu_3sigma_pct:.2f} %", help=tip("CDU"))
    k4.metric("웨이퍼 수율 (±10% Spec)", f"{cdu.within_spec_yield_pct:.1f} %", help="전체 웨이퍼 측정 사이트 중 목표 CD ±10% 스펙 안에 들어온 비율입니다.")

    fig_cdu = plot_wafer_cdu_map(cdu)
    st.pyplot(fig_cdu, alt="300mm 웨이퍼 2D CD 균일도 히트맵과 분포 히스토그램")
    plt.close(fig_cdu)

    with st.expander("🎨 그림과 비유로 이해하기 (피자 토핑 균일도 · 왜 테두리 수율이 떨어질까?)", icon=":material/palette:", expanded=True):
        render_analogy_cards(
            [
                ("🍕 300mm 웨이퍼 CDU = 피자 토핑 균일도", "피자 한 판에서 가운데 조각과 테두리 조각의 크기가 똑같아야 품질이 좋아. 3σ가 작을수록 전체 칩이 고르게 찍힌 거야.", "3σ ≤ 목표 CD의 3%가 양산 목표"),
                ("🌀 스핀 코팅 & 핫플레이트 구배", "웨이퍼를 돌리며 바르면 가장자리 PR 두께가 달라지고, 가열판(PEB)도 테두리 열손실로 온도가 달라져.", "중심(r=0) vs 테두리(r=145mm) 단면 확인"),
                ("🧪 2⁴ DOE = 16번 실험으로 공범 찾기", "변수를 하나씩 바꾸면 'Dose와 Focus가 합쳐질 때의 효과(교호작용)'를 놓쳐. 2수준 DOE가 핵심 인자를 추려줘.", "파란 막대=단일효과, 주황=교호작용"),
            ]
        )
        fig_rad = plot_cdu_radial_decomposition(cdu)
        st.pyplot(fig_rad, alt="웨이퍼 중심에서 가장자리까지의 반경별 PR 두께, PEB 온도, CD 변화 단면도")
        plt.close(fig_rad)

df = _cached_dataset(node_key, n_samples)

with tab2:
    corr = compute_correlation_matrix(df)
    ols = run_ols_regression(df)

    c_left, c_right = st.columns([1.2, 1.0])
    with c_left:
        fig_corr = plot_correlation_heatmap(corr)
        st.pyplot(fig_corr)
        plt.close(fig_corr)
    with c_right:
        st.subheader("표준화 다중선형회귀 (OLS)")
        st.metric("OLS R² / Adj. R² / RMSE", f"{ols.r2:.3f} / {ols.adj_r2:.3f} / {ols.rmse:.2f} nm", help=tip("OLS"))
        st.dataframe(
            ols.coefficients_df.sort_values("abs_std_beta", ascending=False),
            width="stretch",
            hide_index=True,
        )

with tab3:
    runs_df, effects_df = run_2level_factorial_doe(node_key=node_key, underlayer=underlayer)
    fig_doe = plot_doe_effects(effects_df)
    st.pyplot(fig_doe)
    plt.close(fig_doe)

    st.subheader("가상 공정 데이터 미리보기 (Synthetic Fab Dataset)")
    st.dataframe(df.head(20), width="stretch", hide_index=True)
    st.download_button(
        "가상 데이터 CSV 다운로드",
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"synthetic_photo_fab_{node_key}_{n_samples}.csv",
        mime="text/csv",
    )
