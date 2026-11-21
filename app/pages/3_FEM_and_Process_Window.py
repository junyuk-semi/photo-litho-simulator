"""Page 3: Optics-Coupled Focus-Exposure Matrix (FEM), Bossung Plot, Process Window & Defects."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.glossary import render_glossary_toolbar, render_page_concept_guide, tip
from src.physics.constants import EXPOSURE_NODES, ILLUMINATION_PRESETS, PATTERN_PRESETS
from src.physics.exposure_fem import simulate_fem
from src.physics.process_models import tier2_process_shift
from src.visualization.optics_fem_plots import plot_fem_heatmap_and_bossung

st.set_page_config(page_title="FEM & Process Window", page_icon="🎯", layout="wide")

DUV_NODES = [k for k, v in EXPOSURE_NODES.items() if not v.comparison_only]
PAGE3_TERMS = ("FEM", "bossung", "PW", "EL", "contrast", "eta_abs", "collapse", "scumming", "bridging", "notching", "bake", "HMDS", "mack")

with st.sidebar:
    st.header("FEM 공정 조건")
    node_key = st.selectbox("DUV 노광 세대", DUV_NODES, index=2, help=tip("wavelength"))
    node = EXPOSURE_NODES[node_key]
    na_val = st.slider("NA", float(node.na_min), float(node.na_max), float(node.na_default), 0.01, help=tip("NA"))
    illumination = st.selectbox("Illumination (OAI)", list(ILLUMINATION_PRESETS.keys()), index=1, help=tip("OAI"))
    pattern = st.selectbox("Pattern (Dense vs Iso)", list(PATTERN_PRESETS.keys()), index=0, help=tip("pattern"))
    underlayer = st.selectbox("하부막", ["Bare_Si", "SiO2", "PolySi", "Al_Metal"], index=3, help=tip("underlayer"))
    pr_thick = st.slider("PR 두께 (nm)", 60.0, 420.0, float(node.default_pr_thickness_nm), 2.0, help=tip("collapse"))
    barc_thick = st.slider("BARC 두께 (nm)", 0.0, 140.0, 28.0, 1.0, help=tip("BARC"))
    target_cd = st.number_input("목표 CD (nm)", 20.0, 300.0, float(node.default_target_cd_nm), 1.0, help=tip("CD"))

    with st.expander("Tier 2: 베이크·현상·HMDS 보정"):
        peb_temp = st.slider("PEB Temp (°C)", 100.0, 130.0, 115.0, 0.5, help=tip("arrhenius"))
        sb_temp = st.slider("Soft Bake Temp (°C)", 90.0, 130.0, 105.0, 1.0, help=tip("bake"))
        dev_time = st.slider("Development Time (s)", 30.0, 100.0, 60.0, 2.0, help=tip("mack"))
        dev_conc = st.slider("Developer Conc (wt% TMAH)", 2.20, 2.55, 2.38, 0.02, help=tip("mack"))
        hmds_label = st.selectbox("HMDS 처리", ["Vapor (1.0)", "Spin (0.6)", "None (0.0)"], index=0, help=tip("HMDS"))
        hmds_score = {"Vapor (1.0)": 1.0, "Spin (0.6)": 0.6, "None (0.0)": 0.0}[hmds_label]

render_glossary_toolbar("page3", PAGE3_TERMS)

st.title("3️⃣ Focus–Exposure Matrix (FEM) & Process Window 분석")
st.caption("TMM 광학 결합($E_{eff} = E \\cdot \\eta_{abs}$) 기반 Bossung 곡선, 최대 내접 Process Window 및 4대 결함 위험도 평가")

render_page_concept_guide(
    "page3",
    "이 페이지 핵심 용어 & 그래프 읽는 법 (FEM, Bossung, Process Window, EL%, 4대 결함)",
    PAGE3_TERMS,
    quick_summary=(
        "- **왼쪽 그래프 (FEM 히트맵)**: 가로축은 초점(Focus), 세로축은 노광량(Dose), 색상은 선폭(CD)이야. 빨간 점선 사이가 목표 CD **±10% 합격 구역**이고, 그 안에 꽉 들어가는 **노란 사각형이 Process Window(PW)**야.\n"
        "- **오른쪽 그래프 (Bossung Plot)**: 각 Dose별 곡선이 초점에 따라 포물선처럼 휘는 모습을 보여줘. 초록색 띠(±10% 스펙) 안에 오래 머무는 평평한 곡선이 좋은 조건이야.\n"
        "- **결함 진단**: `BARC=0 nm`로 바꾸면 Notching 경고가 뜨고, `HMDS=None` + `PR 두께 증가`를 주면 Pattern Collapse 경고가 뜨는 걸 직접 실험해 봐!"
    ),
)

t2 = tier2_process_shift(
    soft_bake_temp_c=sb_temp,
    peb_temp_c=peb_temp,
    dev_time_s=dev_time,
    dev_conc_wt_pct=dev_conc,
    target_cd_nm=target_cd,
)

fem = simulate_fem(
    node_key=node_key,
    na=na_val,
    illumination=illumination,
    pattern=pattern,
    pr_thickness_nm=pr_thick,
    barc_thickness_nm=barc_thick,
    underlayer_material=underlayer,
    target_cd_nm=target_cd,
    process_cd_bias_nm=t2["process_cd_bias_nm"],
    contrast_modifier=t2["contrast_modifier"],
    hmds_score=hmds_score,
    soft_bake_temp_c=sb_temp,
)
pw = fem.process_window
dfct = fem.defects_at_center

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("최적 Dose / Focus", f"{pw.best_dose_mj_cm2:.2f} mJ/cm² / {pw.best_focus_nm:+.0f} nm", help=tip("FEM"))
m2.metric("PW DOF (최대 내접)", f"{pw.pw_dof_nm:.1f} nm", help=tip("PW"))
m3.metric("PW Exposure Latitude", f"{pw.pw_el_pct:.2f} %", help=tip("EL"))
m4.metric("광학 결합 η_abs / R_sub", f"{fem.optics.effective_dose_factor:.3f} / {fem.optics.substrate_reflectance*100:.1f}%", help=tip("eta_abs"))
m5.metric("종합 결함 위험도", f"{dfct.overall_defect_risk:.1f} / 100", help="4대 결함(Pattern Collapse, Scumming, Bridging/Pinching, Reflective Notching) 중 최대 위험 점수입니다.")

fig = plot_fem_heatmap_and_bossung(fem)
st.pyplot(fig)
plt.close(fig)

st.subheader("Process Window 중심점 정량 결함(Defect) 진단")
d1, d2, d3, d4 = st.columns(4)
d1.metric("Pattern Collapse", f"{dfct.pattern_collapse_risk:.1f}/100", delta=f"AR={dfct.aspect_ratio:.2f}", help=tip("collapse"))
d2.metric("Scumming", f"{dfct.scumming_risk:.1f}/100", help=tip("scumming"))
d3.metric("Bridging / Pinching", f"{dfct.bridging_pinching_risk:.1f}/100", help=tip("bridging"))
d4.metric("Reflective Notching", f"{dfct.notching_risk:.1f}/100", delta=f"SWR={fem.optics.swr_local:.2f}", help=tip("notching"))

if dfct.flags:
    st.error(f"감지된 결함 위험 플래그: {', '.join(dfct.flags)}")
else:
    st.success("현재 Process Window 중심 조건에서 임계 결함 플래그 없음 (안정 공정 구간)")
