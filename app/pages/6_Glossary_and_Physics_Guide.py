"""Page 6: Searchable Photolithography & AI Glossary / Physics Study Guide."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.glossary as _glossary_mod

if getattr(_glossary_mod, "_LOADED_MTIME", 0.0) != os.path.getmtime(_glossary_mod.__file__):
    importlib.reload(_glossary_mod)

from app.glossary import CATEGORIES, GLOSSARY_LIST, render_term_card

st.set_page_config(page_title="용어 사전 & 물리 가이드", page_icon="📖", layout="wide")
st.title("📖 포토공정 · 물리 · AI 용어 백과사전")
st.caption(f"전자공학 학부생 눈높이로 정리한 시뮬레이터 전체 {len(GLOSSARY_LIST)}개 핵심 용어 (직관 + 수식 원리 + 공정 트레이드오프)")

with st.expander("🗺️ 한눈에 보는 포토공정 인과관계 지도 & 입문자 추천 공부 순서", icon=":material/map:", expanded=True):
    st.mermaid_chart(
        """
        flowchart LR
            TF["전 공정: Thin Film & CMP<br/>(하부막 n,k · 단차 Defocus)"] --> OPT["광학·박막: λ, NA, BARC<br/>(CD_min, R_sub, η_abs)"]
            OPT --> EXP["노광·FEM: Dose, Focus<br/>(Bossung, Process Window)"]
            COAT["Track: HMDS, 스핀코팅, PEB, TMAH<br/>(PR두께, Arrhenius L_diff, Mack)"] --> EXP
            EXP --> ADI["ADI 계측 & 데이터 분석<br/>(300mm CDU 3σ, OLS, DOE, SHAP)"]
            ADI --> R2R["실전 Run-to-Run 조치<br/>(1차 → 2차 → 3차 수율 개선)"]
            R2R -. "보정 피드백" .-> COAT
            ADI --> ETCH["후 공정: Etch & 최종 ACI 수율"]
        """,
        alt="전 공정부터 포토, 계측, 반복 수율 개선, 후속 식각까지의 인과관계 지도",
    )

col_search, col_cat = st.columns([2.2, 1.0], vertical_alignment="bottom")
with col_search:
    query = st.text_input(
        "궁금한 단어나 기호 검색",
        placeholder="예: NA, k1, DOF, OAI, TMM, BARC, SWR, Bossung, Process Window, SHAP, 외삽...",
        key="full_glossary_search",
    )
with col_cat:
    category = st.selectbox("카테고리", CATEGORIES, index=0, key="full_glossary_cat")

q = query.strip().lower()
filtered = [
    item
    for item in GLOSSARY_LIST
    if (category == "전체" or item.category == category)
    and (
        not q
        or q in item.term.lower()
        or q in item.key.lower()
        or q in item.short_tip.lower()
        or q in item.intuition.lower()
        or q in item.physics.lower()
        or q in item.tradeoff.lower()
    )
]

st.caption(f"총 {len(GLOSSARY_LIST)}개 용어 중 **{len(filtered)}개** 표시")

if not filtered:
    st.warning("일치하는 용어가 없습니다. 영문 약어(예: CD, NA, BARC, FEM, DOE)나 한글 키워드(예: 정상파, 초점심도, 외삽)로 검색해 보세요.")
else:
    for entry in filtered:
        render_term_card(entry)
