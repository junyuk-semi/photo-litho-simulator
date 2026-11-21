"""Stage 7: Streamlit Multi-Page Integrated Photolithography Process Simulator (Home)."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.glossary as _glossary_mod

if getattr(_glossary_mod, "_LOADED_MTIME", 0.0) != os.path.getmtime(_glossary_mod.__file__):
    importlib.reload(_glossary_mod)

from app.glossary import render_glossary_toolbar, render_page_concept_guide, tip
from src.physics.constants import EXPOSURE_NODES, PARAMETER_SPECS

st.set_page_config(
    page_title="AI Photolithography Simulator",
    page_icon="🔬",
    layout="wide",
)

HOME_TERMS = ("CD", "wavelength", "NA", "pr_tone", "BARC", "FEM", "PW", "CDU", "SHAP", "thin_film", "cmp", "etch_aci", "r2r_apc")
render_glossary_toolbar("home", HOME_TERMS)

st.title("🔬 AI 기반 반도체 포토공정 변수 분석 및 최적화 시뮬레이터")
st.caption("Semiconductor Photolithography Physics, Optics-Coupled FEM, Synthetic Fab Analytics & Run-to-Run Yield Loop")

st.info(
    "본 프로그램은 **① 원리 공부용(1~6페이지)**과 **② 실전 Fab 공정 사이클 & 반복 수율 개선용(7페이지)** 두 모드를 모두 지원합니다. "
    "모든 계산은 표준 물리 방정식(Rayleigh, 2×2 TMM, Bossung FEM, Meyerhofer, Arrhenius PEB, Mack)에 기반한 가상 공정 데이터입니다.",
    title="공부용 + 실전 Fab 사이클 듀얼 모드 안내",
)

st.success(
    "각 슬라이더·지표 옆의 **물음표(`?`) 아이콘**에 마우스를 올리면 짧은 설명이 바로 뜨고, "
    "각 페이지 상단의 **🎨 그림과 비유로 이해하기** 패널과 **6️⃣ 용어 사전**에서 모든 물리·AI 개념을 학부생 눈높이로 배울 수 있습니다.",
    title="처음이거나 용어가 헷갈릴 때 활용법",
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("지원 노광 세대", "DUV 3종 + EUV 비교", help=tip("wavelength"))
col2.metric("관리 공정 변수", f"{len(PARAMETER_SPECS)}개 (Tier 1 & 2)", help="핵심 광학·노광 변수(Tier 1)와 코팅·베이크·현상 변수(Tier 2) 전체를 체계적으로 관리합니다.")
col3.metric("핵심 출력 KPI", "7대 지표 + ACI 수율", help="CD, CDU(3σ), Resolution, I(z), Reflectance, Defect Risk, Process Window 및 Etch ACI 수율입니다.")
col4.metric("실전 워크플로우", "1차 → 2차 → 3차 수율 개선", help=tip("r2r_apc"))

with st.expander("🎨 사진 인화로 1분 이해하는 포토공정 (비유 & 전체 지도)", icon=":material/lightbulb:", expanded=True):
    st.markdown(
        """
        포토리소그래피를 **'실리콘 웨이퍼 위에 빛으로 회로 도장을 파내는 초정밀 사진 인화'**에 비유하면 전체 흐름이 바로 잡혀:

        | 실제 사진 인화 · 판화 비유 | 반도체 포토공정 단계 | 핵심 물리 · 시뮬레이터 페이지 |
        | :--- | :--- | :--- |
        | **도화지 깔기 & 책상 평탄화** | 전 공정 (`Thin Film` 증착 · `CMP` 연마) | 하부막 반사율·단차 Defocus 유발 (`7페이지`) |
        | **붓 굵기 & 카메라 조리개 조절** | 노광 광원(`λ`), 렌즈(`NA`), 조명(`OAI`) | $CD_{min} = k_1\\lambda/NA$, $DOF \\propto \\lambda/NA^2$ (`1페이지`) |
        | **바닥 거울에 무반사 코팅 깔기** | `BARC` + `PR` 스핀코팅 | 빛 반사·정상파($I(z)$)·Swing 억제 (`2페이지`) |
        | **카메라 초점·노출 시간 맞춰 찍기** | 노광 (`FEM`: Focus × Dose) | Bossung 곡선, 안전구역 Process Window (`3페이지`) |
        | **현상액으로 씻고 오븐에 굽기** | `PEB` 산 확산 · `TMAH` 현상 · 300mm `CDU` | 웨이퍼 3σ 균일도 & 데이터 분석 (`4~5페이지`) |
        | **탄착점 보고 조준경 보정해 재사격** | `ADI` 계측 → 분석 보고서 → `N+1차` 보정 → `Etch` | 사이클별 반복 수율 개선 (`7페이지`) |
        """
    )
    st.mermaid_chart(
        """
        flowchart LR
            subgraph STUDY["📚 공부용 모드 (1~6페이지)"]
                S1["1. 해상도·DOF<br/>(붓굵기·조리개)"] --> S2["2. 박막간섭·BARC<br/>(정상파·반사손실)"]
                S2 --> S3["3. FEM·결함<br/>(초점×광량 안전구역)"]
                S3 --> S4["4. 웨이퍼 CDU·통계<br/>(DOE·회귀)"]
                S4 --> S5["5. ML·SHAP·외삽<br/>(AI 보조·한계)"]
            end
            subgraph FAB["🏭 실전 Fab 모드 (7페이지)"]
                F1["전 공정<br/>Thin Film & CMP"] --> F2["포토 Track·Scanner<br/>1차 → 2차 → 3차"]
                F2 --> F3["ADI 계측 +<br/>분석·조치 보고서"]
                F3 -- "NG 시 조치 반영 재투입" --> F2
                F3 -- "OK 시 출하" --> F4["후 공정 Etch<br/>최종 ACI 수율"]
            end
        """,
        alt="공부용 모듈과 실전 Fab 반복 수율 개선 사이클 연결 흐름도",
    )

render_page_concept_guide(
    "home",
    "포토공정 핵심 요약 & 용어 바로 보기",
    HOME_TERMS,
    quick_summary=(
        "- **공부용(1~6페이지)**: 각 물리 공식과 그래프가 왜 그런 모양이 나오는지 하나씩 실험하고 비유와 그림으로 이해하는 공간.\n"
        "- **실전용(7페이지)**: `전 공정(Thin Film·CMP) → 포토 8단계 → ADI 계측 → Etch` 순서대로 1차·2차·3차 시뮬레이션을 돌리며 분석 보고서와 조치사항을 따라 수율을 98%+까지 끌어올리는 공간."
    ),
)

st.divider()

st.subheader("시뮬레이터 모듈 구성 (좌측 사이드바에서 이동)")
m1, m2 = st.columns(2)
with m1:
    st.markdown(
        """
        #### 📚 공부용 모듈 (원리 · 비유 · 시각화)
        1. **1️⃣ Resolution & DOF** — Rayleigh 해상도, 렌즈 집광 각도 도해, Immersion & OAI 비유
        2. **2️⃣ Optics & BARC (TMM)** — 다층 박막 단면 빛 경로, Standing Wave, Swing Curve & BARC
        3. **3️⃣ FEM & Process Window** — Bossung 곡선, 안전구역 PW, PR 단면 모양 & 4대 결함 도해
        4. **4️⃣ Wafer CDU & Data Analysis** — 300mm 웨이퍼 맵, 반경별 두께/온도 단면도, OLS & $2^4$ DOE
        5. **5️⃣ ML & Process Optimization** — Linear/RF/XGBoost 비교, SHAP 원인 분해, 외삽 한계 증명
        6. **6️⃣ 용어 사전 & 물리 가이드** — 48개 핵심 용어의 직관 + 수식 원리 + 인과관계 지도
        """
    )
with m2:
    st.markdown(
        """
        #### 🏭 실전 Fab 워크플로우 모듈
        7. **7️⃣ 실전 Fab 공정 사이클 & 반복 수율 개선**
           - **실제 공정 순서 그대로**: 전 공정(`Thin Film`, `CMP` 단차) → 코팅(`HMDS`, `BARC`, `Spin`) → 베이크(`SB`, `PEB`) → 노광(`Dose`, `Focus`, `OAI`) → 현상(`TMAH`) → 후공정(`Etch Bias`, `ACI` 수율)
           - **회차별 반복 수율 개선**: `1차 → 2차 → 3차` 시뮬레이션을 돌리며 수율 상승 곡선 및 300mm 웨이퍼 맵 변화 누적 비교
           - **사이클별 자동 보고서 & 조치사항(CAPA)**: 매 회차 종료 시 **결과 성적표 + 원인 분해 데이터 분석 + 향후 필요한 조치사항** 보고서 작성 및 원클릭 차기 세팅 반영
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
