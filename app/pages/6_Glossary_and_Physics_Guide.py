"""Page 6: Searchable Photolithography & AI Glossary / Physics Study Guide."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.glossary import CATEGORIES, GLOSSARY_LIST, render_term_card

st.set_page_config(page_title="용어 사전 & 물리 가이드", page_icon="📖", layout="wide")
st.title("📖 포토공정 · 물리 · AI 용어 백과사전")
st.caption("전자공학 학부생 눈높이로 정리한 시뮬레이터 전체 44개 핵심 용어 (직관 + 수식 원리 + 공정 트레이드오프)")

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
