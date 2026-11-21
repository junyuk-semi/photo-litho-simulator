"""Page 2: Multilayer Thin-Film Optics (TMM/S-Matrix), Standing Wave, Swing Curve & BARC."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.glossary as _glossary_mod

if getattr(_glossary_mod, "_LOADED_MTIME", 0.0) != os.path.getmtime(_glossary_mod.__file__):
    importlib.reload(_glossary_mod)

from app.glossary import render_analogy_cards, render_glossary_toolbar, render_page_concept_guide, tip
from src.physics.constants import EXPOSURE_NODES, get_optical_constants
from src.physics.optics_tmm import (
    build_litho_stack,
    compute_swing_curve,
    get_ambient_for_node,
    optimize_barc_thickness,
    simulate_multilayer_optics,
)
from src.visualization.optics_fem_plots import (
    plot_standing_wave_comparison,
    plot_swing_curve_and_barc_opt,
)
from src.visualization.study_visuals import plot_multilayer_stack_intuition

st.set_page_config(page_title="Optics & BARC (TMM)", page_icon="🌈", layout="wide")

DUV_NODES = [k for k, v in EXPOSURE_NODES.items() if not v.comparison_only]
PAGE2_TERMS = ("tmm", "nk", "alpha", "RTA", "standing_wave", "SWR", "swing_curve", "BARC", "underlayer", "eta_abs")

with st.sidebar:
    st.header("박막 스택 설정")
    node_key = st.selectbox("DUV 노광 세대", DUV_NODES, index=2, help=tip("wavelength"))
    node = EXPOSURE_NODES[node_key]
    wl = node.wavelength_nm
    ambient = get_ambient_for_node(node_key)

    underlayer = st.selectbox("하부막 (Underlayer)", ["Bare_Si", "SiO2", "PolySi", "Al_Metal"], index=3, help=tip("underlayer"))
    ul_thick = st.slider("Underlayer 두께 (nm)", 0.0, 300.0, 100.0, 5.0, help=tip("underlayer"))
    pr_thick = st.slider("PR 두께 (nm)", 60.0, 450.0, float(node.default_pr_thickness_nm), 2.0, help=tip("swing_curve"))
    barc_thick = st.slider("BARC 두께 (nm, 0=미적용)", 0.0, 140.0, 30.0, 1.0, help=tip("BARC"))

    with st.expander("PR / BARC 굴절률(n, k) 직접 조절"):
        pr_def = get_optical_constants("PR_DUV", wl)
        barc_def = get_optical_constants("BARC_Organic", wl)
        pr_n = st.slider("PR n", 1.40, 2.00, float(pr_def.n), 0.01, help=tip("nk"))
        pr_k = st.slider("PR k", 0.00, 0.15, float(pr_def.k), 0.005, help=tip("nk"))
        barc_n = st.slider("BARC n", 1.40, 2.10, float(barc_def.n), 0.01, help=tip("nk"))
        barc_k = st.slider("BARC k", 0.00, 0.90, float(barc_def.k), 0.01, help=tip("nk"))

render_glossary_toolbar("page2", PAGE2_TERMS)

st.title("2️⃣ 다층 박막 광학 & BARC 시뮬레이션 (2×2 TMM)")
st.caption("Fresnel 반사·투과, Beer-Lambert 흡수, PR 내부 Standing Wave $I(z)$, Swing Curve 및 BARC 최적화")

render_page_concept_guide(
    "page2",
    "이 페이지 핵심 용어 & 물리 원리 쉽게 보기 (TMM, 정상파, SWR, Swing Curve, BARC, η_abs)",
    PAGE2_TERMS,
    quick_summary=(
        "- **왜 바닥 반사가 문제일까?**: PR 아래의 실리콘/알루미늄이 거울처럼 빛을 반사하면 입사광과 반사광이 겹쳐 **정상파(Standing Wave)**가 생기고, PR 측벽이 계단처럼 울퉁불퉁해져.\n"
        "- **Swing Curve**: PR 두께가 몇 nm만 달라져도 박막 간섭 위상이 바뀌어 반사율과 흡수 광량($\\eta_{abs}$)이 롤러코스터처럼 출렁여.\n"
        "- **BARC의 원리**: PR과 하부막 사이에 $\\lambda/(4n_{BARC})$ 부근 두께의 반사방지막을 깔면 **상쇄간섭 + 흡수**로 $R_{sub}$를 2% 미만으로 눌러줘. 사이드바에서 BARC 두께를 `0 nm`와 `최적 두께`로 바꿔 비교해 봐!"
    ),
)

stack_no_barc = build_litho_stack(
    wl, ambient, pr_thick, 0.0, underlayer, ul_thick, pr_n=pr_n, pr_k=pr_k, barc_n=barc_n, barc_k=barc_k
)
stack_barc = build_litho_stack(
    wl, ambient, pr_thick, barc_thick, underlayer, ul_thick, pr_n=pr_n, pr_k=pr_k, barc_n=barc_n, barc_k=barc_k
)
res_off = simulate_multilayer_optics(stack_no_barc, wl)
res_on = simulate_multilayer_optics(stack_barc, wl)

barc_opt = optimize_barc_thickness(
    wl, ambient, pr_thick, underlayer, ul_thick, barc_n=barc_n, barc_k=barc_k
)
opt_d = float(barc_opt["optimal_barc_nm"])

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("하부막 반사율 R_sub", f"{res_on.substrate_reflectance*100:.2f}%", delta=f"{(res_on.substrate_reflectance - res_off.substrate_reflectance)*100:+.2f}% vs No BARC", delta_color="inverse", help=tip("RTA"))
c2.metric("총 반사율 R / 흡수율 A", f"{res_on.reflectance*100:.1f}% / {res_on.absorptance*100:.1f}%", help=tip("RTA"))
c3.metric("Standing Wave Ratio", f"{res_on.swr_local:.2f}", delta=f"{res_on.swr_local - res_off.swr_local:+.2f}", delta_color="inverse", help=tip("SWR"))
c4.metric("유효 흡수계수 η_abs", f"{res_on.effective_dose_factor:.3f}", help=tip("eta_abs"))
c5.metric("TMM 최적 BARC 두께", f"{opt_d:.1f} nm", delta=f"최소 R_sub={barc_opt['min_substrate_reflectance']*100:.2f}%", help=tip("BARC"))

st.caption(
    f"PR Beer-Lambert 흡수계수 α = {res_on.pr_absorption_coeff_um_inv:.2f} μm⁻¹ | "
    f"이론 정상파 주기 λ/(2n_PR) = {res_on.standing_wave_period_nm:.2f} nm | "
    f"에너지 보존 검증 R+T+A = {res_on.reflectance + res_on.transmittance + res_on.absorptance:.6f}"
)

with st.expander("🎨 그림과 비유로 이해하기 (거울 반사 · 줄넘기 정상파 · 안경 무반사 코팅 BARC)", icon=":material/palette:", expanded=True):
    render_analogy_cards(
        [
            ("🪞 하부막 = 바닥 거울", "무광 종이(SiO₂)와 은박지(Al 금속)는 반사율이 달라. 바닥이 번쩍이면 빛이 되튀어 올라와.", "R_sub: PR 바닥에서 되돌아오는 반사율"),
            ("〰️ 정상파 = 줄넘기 파도", "위에서 내려오는 빛과 바닥 반사광이 겹쳐 PR 안에 밝고 어두운 줄무늬가 생겨 측벽이 계단처럼 깎여.", "주기 = λ/(2·n_PR), SWR = I_max/I_min"),
            ("🕶️ BARC = 무반사 코팅 + 스펀지", "두께(λ/4n)로 반사파 위상을 180° 어긋나게 지우고, 흡수(k)로 남은 빛을 먹어 바닥 반사를 2% 밑으로 눌러줘.", "최적 BARC → Swing 평탄화"),
        ]
    )
    fig_int2 = plot_multilayer_stack_intuition(stack_barc, res_off, res_on, barc_thick)
    st.pyplot(fig_int2, alt="다층 박막 단면 빛 반사 경로와 BARC 유무에 따른 PR 측벽 정상파 비교 도해")
    plt.close(fig_int2)

fig_sw = plot_standing_wave_comparison(res_off, res_on, underlayer, barc_thick)
st.pyplot(fig_sw)
plt.close(fig_sw)

swing_off = compute_swing_curve(
    wl, ambient, (max(60.0, pr_thick - 60.0), pr_thick + 120.0), 90, 0.0, underlayer, ul_thick,
    pr_n=pr_n, pr_k=pr_k, barc_n=barc_n, barc_k=barc_k
)
swing_opt = compute_swing_curve(
    wl, ambient, (max(60.0, pr_thick - 60.0), pr_thick + 120.0), 90, opt_d, underlayer, ul_thick,
    pr_n=pr_n, pr_k=pr_k, barc_n=barc_n, barc_k=barc_k
)
fig_swing = plot_swing_curve_and_barc_opt(swing_off, swing_opt, barc_opt, underlayer)
st.pyplot(fig_swing)
plt.close(fig_swing)
