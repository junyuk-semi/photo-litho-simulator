"""Page 1: Rayleigh Resolution, High-NA/Immersion DOF, OAI Scaling & Exposure Energy."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.glossary as _glossary_mod

if getattr(_glossary_mod, "_LOADED_MTIME", 0.0) != os.path.getmtime(_glossary_mod.__file__):
    importlib.reload(_glossary_mod)

from app.glossary import render_analogy_cards, render_glossary_toolbar, render_page_concept_guide, tip
from src.physics.constants import EXPOSURE_NODES, ILLUMINATION_PRESETS, PATTERN_PRESETS
from src.physics.resolution import (
    analyze_node,
    compare_all_nodes,
    exposure_dose,
    required_exposure_time,
)
from src.visualization.resolution_plots import (
    plot_node_comparison,
    plot_resolution_dof_tradeoff,
    plot_resolution_vs_na,
)
from src.visualization.study_visuals import plot_rayleigh_aperture_intuition

st.set_page_config(page_title="Resolution & DOF", page_icon="📐", layout="wide")

PAGE1_TERMS = ("CD", "wavelength", "NA", "k1", "DOF", "immersion", "OAI", "pattern", "exposure_dose")

with st.sidebar:
    st.header("광학 변수 설정")
    node_key = st.selectbox("노광 세대 (Node)", list(EXPOSURE_NODES.keys()), index=2, help=tip("wavelength"))
    node = EXPOSURE_NODES[node_key]
    na_val = st.slider("Numerical Aperture (NA)", float(node.na_min), float(node.na_max), float(node.na_default), 0.01, help=tip("NA"))
    k1_val = st.slider("Process Factor (k1)", 0.25, 0.60, float(node.k1_default), 0.01, help=tip("k1"))
    k2_val = st.slider("DOF Factor (k2)", 0.30, 0.80, float(node.k2_default), 0.02, help=tip("DOF"))
    illumination = st.selectbox("Illumination (OAI)", list(ILLUMINATION_PRESETS.keys()), index=1, help=tip("OAI"))
    pattern = st.selectbox("Pattern Type", list(PATTERN_PRESETS.keys()), index=0, help=tip("pattern"))
    target_cd = st.number_input("목표 CD (nm)", min_value=5.0, max_value=500.0, value=float(node.default_target_cd_nm), step=1.0, help=tip("CD"))
    include_euv = st.checkbox("EUV (13.5 nm) 비교 곡선 포함", value=True, help="EUV는 파장이 13.5nm로 매우 짧아 해상도가 높고, NA가 0.33으로 낮아 DOF도 유리합니다.")

render_glossary_toolbar("page1", PAGE1_TERMS)

st.title("1️⃣ 해상도(Resolution) & 초점심도(DOF) 계산기")
st.caption("Rayleigh Criterion ($CD = k_1\\lambda/NA$), High-NA/Immersion DOF 및 OAI 조명계 분석")

render_page_concept_guide(
    "page1",
    "이 페이지 핵심 용어 & 물리 원리 쉽게 보기 (λ, NA, k1, DOF, Immersion, OAI)",
    PAGE1_TERMS,
    quick_summary=(
        "- **핵심 트레이드오프**: $CD_{min} = k_1\\frac{\\lambda}{NA}$, $DOF \\propto \\frac{\\lambda}{NA^2}$. "
        "즉, **NA를 키우면 선폭은 작아지지만 초점 여유(DOF)가 제곱으로 급감**해.\n"
        "- **해결책 1 (Immersion)**: 렌즈와 웨이퍼 사이에 물($n=1.44$)을 채우면 $NA$를 1.35까지 높이고 같은 $NA$에서 DOF도 ~44% 늘어나.\n"
        "- **해결책 2 (OAI)**: Annular/Dipole처럼 빛을 비스듬히 쏘면 Dense 패턴의 유효 $k_1$이 줄고 DOF가 커져."
    ),
)

res = analyze_node(
    node_key=node_key,
    na=na_val,
    k1=k1_val,
    k2=k2_val,
    illumination=illumination,
    pattern=pattern,
    target_cd_nm=target_cd,
)

if res.comparison_only:
    st.warning("EUV (13.5 nm)는 반사광학계·확률적 노이즈 특성이 달라 본 시뮬레이터에서는 2단계 해상도/DOF 비교 전용으로만 제공됩니다.")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("유효 k1 (OAI 반영)", f"{res.k1_effective:.3f}", help=tip("k1"))
c2.metric("최소 해상도 CD_min", f"{res.min_cd_nm:.2f} nm", help=tip("CD"))
c3.metric("High-NA DOF", f"{res.dof_high_na_nm:.1f} nm", delta=f"Paraxial 대비 {res.dof_high_na_nm - res.dof_paraxial_nm:+.1f} nm", help=tip("DOF"))
c4.metric("최소 Pitch", f"{res.min_pitch_nm:.1f} nm", help=tip("pattern"))
c5.metric("해상 가능 여부", "가능 (PASS)" if res.is_resolvable else "한계 초과 (FAIL)", delta=f"Margin {res.resolution_margin_nm:+.1f} nm", help="목표 CD가 이론적 최소 해상도 CD_min 이상이면 단일 노광으로 해상 가능합니다.")

with st.expander("🎨 그림과 비유로 10초 이해하기 (붓 굵기 · 조리개 · 사입사 가로등)", icon=":material/palette:", expanded=True):
    render_analogy_cards(
        [
            ("🖌️ 파장(λ) = 붓 굵기", "굵은 유성 매직(248nm)보다 0.1mm 샤프(193nm/EUV)가 훨씬 작은 글씨를 번짐 없이 그릴 수 있어.", "Rayleigh 식: CD_min ∝ λ"),
            ("📷 NA = 카메라 조리개", "렌즈가 넓게 빛을 모을수록(NA↑) 디테일은 살지만, 아웃포커싱처럼 초점이 맞는 범위(DOF)가 제곱으로 얇아져.", "DOF ∝ λ / NA² (핵심 트레이드오프)"),
            ("🔦 OAI = 비스듬한 가로등", "빛을 수직 대신 비스듬히 쏘면 좁은 틈의 회절광이 렌즈 안으로 살아 들어오고, 물(Immersion)은 빛을 더 크게 꺾어줘.", "유효 k1↓, Dense DOF↑"),
        ]
    )
    fig_int1 = plot_rayleigh_aperture_intuition(
        wavelength_nm=res.wavelength_nm,
        na=res.na,
        n_fluid=res.n_fluid,
        illumination=illumination,
        min_cd_nm=res.min_cd_nm,
        target_cd_nm=target_cd,
        dof_nm=res.dof_high_na_nm,
    )
    st.pyplot(fig_int1, alt="현재 NA, 매질 굴절률, 파장에 따른 렌즈 집광 각도와 DOF 초점 폭 도해")
    plt.close(fig_int1)

tab1, tab2, tab3, tab4 = st.tabs(["파장·NA별 해상도", "CD vs DOF 트레이드오프", "4대 노드 비교", "노광 에너지 계산기"])

with tab1:
    fig1 = plot_resolution_vs_na(k1=k1_val, illumination=illumination, include_euv=include_euv)
    st.pyplot(fig1)
    plt.close(fig1)

with tab2:
    wl_trade = 193.0 if node.comparison_only else node.wavelength_nm
    fig2 = plot_resolution_dof_tradeoff(
        wavelength_nm=wl_trade, k1=k1_val, k2=k2_val, illumination=illumination, pattern=pattern
    )
    st.pyplot(fig2)
    plt.close(fig2)

with tab3:
    fig3 = plot_node_comparison(illumination=illumination, pattern=pattern)
    st.pyplot(fig3)
    plt.close(fig3)
    all_rows = [
        {
            "Node": r.node_key,
            "λ (nm)": r.wavelength_nm,
            "NA": r.na,
            "n_fluid": r.n_fluid,
            "k1_eff": round(r.k1_effective, 3),
            "Min CD (nm)": round(r.min_cd_nm, 2),
            "High-NA DOF (nm)": round(r.dof_high_na_nm, 1),
            "Paraxial DOF (nm)": round(r.dof_paraxial_nm, 1),
            "Note": "Comparison Only" if r.comparison_only else "DUV Core",
        }
        for r in compare_all_nodes(illumination=illumination, pattern=pattern)
    ]
    st.dataframe(pd.DataFrame(all_rows), width="stretch", hide_index=True)

with tab4:
    st.markdown("**노광 에너지 관계식**: $\\text{Exposure Dose } (\\text{mJ/cm}^2) = \\text{Light Intensity } (\\text{mW/cm}^2) \\times \\text{Exposure Time } (\\text{s})$")
    ec1, ec2 = st.columns(2)
    with ec1:
        i0 = st.number_input("입사 광도 Light Intensity (mW/cm²)", 0.1, 1000.0, 280.0, 5.0, help=tip("exposure_dose"))
        t_exp = st.number_input("노광 시간 Exposure Time (s)", 0.001, 60.0, 0.10, 0.01, format="%.3f", help=tip("exposure_dose"))
        st.metric("계산된 Exposure Dose", f"{exposure_dose(i0, t_exp):.2f} mJ/cm²", help=tip("exposure_dose"))
    with ec2:
        target_d = st.number_input("목표 Exposure Dose (mJ/cm²)", 1.0, 200.0, 28.0, 1.0, help=tip("exposure_dose"))
        st.metric("필요 노광 시간 (현재 광도 기준)", f"{required_exposure_time(target_d, i0):.4f} s", help="목표 Dose를 광도 I0로 나눈 값입니다. 광도가 떨어지면 노광 시간을 늘려야 합니다.")
