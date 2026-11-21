"""Stage 7: Streamlit Multi-Page Integrated Photolithography Process Simulator (Home)."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.glossary import render_glossary_toolbar, render_page_concept_guide, tip
from src.physics.constants import EXPOSURE_NODES, PARAMETER_SPECS

st.set_page_config(
    page_title="AI Photolithography Simulator",
    page_icon="🔬",
    layout="wide",
)

HOME_TERMS = ("CD", "wavelength", "NA", "pr_tone", "BARC", "FEM", "PW", "CDU", "SHAP")
render_glossary_toolbar("home", HOME_TERMS)

st.title("🔬 AI 기반 반도체 포토공정 변수 분석 및 최적화 시뮬레이터")
st.caption("Semiconductor Photolithography Physics, Optics-Coupled FEM, Synthetic Fab Analytics & ML Optimization")

st.info(
    "본 프로그램의 모든 계산과 데이터는 실제 제조사 내부 레시피가 아니라, 표준 광학·리소그래피 물리 방정식"
    "(Rayleigh, 2×2 TMM/S-Matrix 박막간섭, Bossung FEM, Meyerhofer 스핀코팅, Arrhenius PEB, Mack 현상 모델)과 "
    "현실적 공정 산포 모델을 결합해 생성한 **가상 공정 데이터**입니다.",
    title="가상 시뮬레이션 데이터 안내 (Synthetic Data Notice)",
)

st.success(
    "각 슬라이더·지표 옆의 **물음표(`?`) 아이콘**에 마우스를 올리면 짧은 설명이 바로 뜨고, "
    "좌측 사이드바의 **'용어 사전 바로 열기'** 버튼이나 **6️⃣ 용어 사전** 페이지에서 모든 물리·AI 개념을 학부생 눈높이로 검색할 수 있습니다.",
    title="처음이거나 용어가 헷갈릴 때 활용법",
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("지원 노광 세대", "DUV 3종 + EUV 비교", help=tip("wavelength"))
col2.metric("관리 공정 변수", f"{len(PARAMETER_SPECS)}개 (Tier 1 & 2)", help="핵심 광학·노광 변수(Tier 1)와 코팅·베이크·현상 변수(Tier 2) 전체를 체계적으로 관리합니다.")
col3.metric("핵심 출력 KPI", "7대 공정 지표", help="CD, CD Uniformity(3σ), Resolution, Light Intensity I(z), Reflectance, Defect Risk, Process Window 7개 지표입니다.")
col4.metric("물리-ML 결합", "TMM ↔ FEM ↔ XGBoost/SHAP", help=tip("eta_abs"))

render_page_concept_guide(
    "home",
    "포토공정 전체 흐름 1분 이해하기 (초심자·학부생 가이드)",
    HOME_TERMS,
    quick_summary=(
        "포토리소그래피는 **빛으로 마스크 그림자를 웨이퍼 위 감광액(PR)에 찍어내는 사진 현상 과정**이야.\n"
        "1. **해상도(1페이지)**: 얼마나 얇은 선(CD)까지 그릴 수 있는지 빛의 파장($\\lambda$)과 렌즈($NA$)로 결정해.\n"
        "2. **광학·BARC(2페이지)**: PR 바닥에서 빛이 반사돼 생기는 정상파를 BARC로 억제해.\n"
        "3. **FEM·Process Window(3페이지)**: 초점(Focus)과 노광량(Dose)이 흔들려도 CD가 ±10% 안에 버티는 안전 구간을 찾아.\n"
        "4. **웨이퍼 CDU·통계(4페이지)**: 300mm 웨이퍼 전체 균일도(3σ)와 변수 영향력을 DOE/회귀로 분석해.\n"
        "5. **ML·최적화(5페이지)**: XGBoost/SHAP으로 원인 분석·최적 레시피를 찾고, ML이 물리를 대체 못 하는 외삽 한계까지 확인해."
    ),
)

st.divider()

st.subheader("시뮬레이터 모듈 구성 (좌측 사이드바에서 이동)")
m1, m2 = st.columns(2)
with m1:
    st.markdown(
        """
        1. **1️⃣ Resolution & DOF** — Rayleigh 해상도($CD = k_1\\lambda/NA$), High-NA/Immersion DOF, OAI 조명계 효과, EUV 비교 및 노광에너지($E = I_0 \\cdot t$)
        2. **2️⃣ Optics & BARC (TMM)** — 다층 박막 간섭, 하부막(Bare Si/SiO₂/Poly-Si/Al) 반사율, PR 내부 Standing Wave $I(z)$, Swing Curve 및 최적 BARC 두께 탐색
        3. **3️⃣ FEM & Process Window** — 광학 결합($E_{eff} = E \\cdot \\eta_{abs}$) Focus–Exposure Matrix, Bossung 곡선, 최대 내접 Process Window(DOF @ EL%) 및 4대 결함 위험도
        """
    )
with m2:
    st.markdown(
        """
        4. **4️⃣ Wafer CDU & Data Analysis** — 300mm 웨이퍼 2D CDU 맵($3\\sigma$), LHS 기반 가상 Fab 데이터 생성, 상관관계 히트맵, 표준화 OLS 회귀 및 $2^4$ DOE 교호작용 분석
        5. **5️⃣ ML & Process Optimization** — Linear / RF / XGBoost CD 예측 벤치마크, 실시간 CD 예측기, SHAP 산포 원인 분해, 물리 검증 최적 레시피 탐색 및 **외삽 한계 증명 실험**
        6. **6️⃣ 용어 사전 & 물리 가이드** — 시뮬레이터 전체 44개 용어의 쉬운 직관 + 수식 원리 + 트레이드오프 검색 백과사전
        """
    )

st.subheader("지원 노광 세대 프리셋 기준선 (Positive PR, 1D Line/Space)")
node_rows = [
    {
        "Node Key": n.key,
        "이름": n.name,
        "파장 λ (nm)": n.wavelength_nm,
        "기본 NA": n.na_default,
        "매질 굴절률 n": n.n_fluid,
        "기본 k1": n.k1_default,
        "기본 PR 두께 (nm)": n.default_pr_thickness_nm,
        "목표 CD (nm)": n.default_target_cd_nm,
        "비고": "2단계 해상도/DOF 비교 전용" if n.comparison_only else "전체 시뮬레이터 지원",
    }
    for n in EXPOSURE_NODES.values()
]
st.dataframe(node_rows, width="stretch", hide_index=True)

with st.expander("실제 양산 Fab 공정과 시뮬레이터의 차이 (한계점 요약)"):
    st.markdown(
        """
        - **1D 평탄 박막 vs 3D 단차(Topography)**: 실제 소자의 알루미늄 경사면 반사($\\theta=60^\\circ\\sim70^\\circ$)나 3D 회절(RCWA/FDTD)은 1D TMM에서 근사되지 않음.
        - **High-NA 편광 & 렌즈 수차**: ArFi($NA=1.35$)에서의 벡터 편광 효과와 Zernike 렌즈 수차는 스칼라 근사로 단순화됨.
        - **CAR 확률적 노이즈(Stochastics)**: 미세 패턴의 LER/LWR 및 EUV 광자 샷 노이즈는 정규 산포 항으로 근사됨.
        - **ADI vs ACI**: 본 시뮬레이터는 현상 후(ADI) CD 기준이며, 실제 소자 적용 시 식각 바이어스(Etch Bias) 및 실측 CD-SEM 캘리브레이션이 필요함.
        """
    )
