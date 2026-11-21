"""Page 7: Real-World Fab Sequential Photo Flow, Run-to-Run Cycle & Engineering Report."""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import fields
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

from app.glossary import render_glossary_toolbar, render_page_concept_guide, tip
from src.fab_cycle import (
    CycleResult,
    FabRecipe,
    build_cumulative_summary_markdown,
    preset_recipes,
    run_fab_cycle,
)
from src.physics.constants import EXPOSURE_NODES, ILLUMINATION_PRESETS, PATTERN_PRESETS
from src.visualization.fab_cycle_plots import (
    plot_cycle_progression,
    plot_cycle_wafer_comparison,
    plot_root_cause_pareto,
)

st.set_page_config(page_title="Fab Cycle & Yield Loop", page_icon="🏭", layout="wide")

DUV_NODES = [k for k, v in EXPOSURE_NODES.items() if not v.comparison_only]
UNDERLAYERS = ["Al_Metal", "PolySi", "SiO2", "Bare_Si"]
HMDS_OPTIONS = {"Vapor (1.0)": 1.0, "Spin (0.6)": 0.6, "None (0.0)": 0.0}
HMDS_LABELS = {1.0: "Vapor (1.0)", 0.6: "Spin (0.6)", 0.0: "None (0.0)"}

PAGE7_TERMS = ("thin_film", "cmp", "BARC", "spin_coating", "exposure_dose", "FEM", "CDU", "etch_aci", "r2r_apc")


def _set_recipe_to_state(recipe: FabRecipe) -> None:
    """Sync all FabRecipe fields into Streamlit widget keys before rerun."""
    for f in fields(FabRecipe):
        st.session_state[f"fab_{f.name}"] = getattr(recipe, f.name)
    st.session_state["fab_hmds_label"] = HMDS_LABELS.get(round(recipe.hmds_score, 1), "Vapor (1.0)")


def _read_recipe_from_state() -> FabRecipe:
    """Build FabRecipe from current widget states."""
    hmds_lbl = st.session_state.get("fab_hmds_label", "Vapor (1.0)")
    return FabRecipe(
        node_key=str(st.session_state["fab_node_key"]),
        underlayer_material=str(st.session_state["fab_underlayer_material"]),
        underlayer_thickness_nm=float(st.session_state["fab_underlayer_thickness_nm"]),
        cmp_dishing_defocus_nm=float(st.session_state["fab_cmp_dishing_defocus_nm"]),
        cmp_focus_sigma_nm=float(st.session_state["fab_cmp_focus_sigma_nm"]),
        hmds_score=float(HMDS_OPTIONS.get(hmds_lbl, 1.0)),
        barc_thickness_nm=float(st.session_state["fab_barc_thickness_nm"]),
        spin_speed_rpm=float(st.session_state["fab_spin_speed_rpm"]),
        pr_viscosity_cp=float(st.session_state["fab_pr_viscosity_cp"]),
        dispense_volume_ml=float(st.session_state["fab_dispense_volume_ml"]),
        pr_radial_range_nm=float(st.session_state["fab_pr_radial_range_nm"]),
        soft_bake_temp_c=float(st.session_state["fab_soft_bake_temp_c"]),
        peb_temp_c=float(st.session_state["fab_peb_temp_c"]),
        peb_radial_range_c=float(st.session_state["fab_peb_radial_range_c"]),
        na=float(st.session_state["fab_na"]),
        illumination=str(st.session_state["fab_illumination"]),
        pattern=str(st.session_state["fab_pattern"]),
        exposure_dose_mj_cm2=float(st.session_state["fab_exposure_dose_mj_cm2"]),
        focus_offset_nm=float(st.session_state["fab_focus_offset_nm"]),
        dose_noise_sigma_pct=float(st.session_state["fab_dose_noise_sigma_pct"]),
        dev_time_s=float(st.session_state["fab_dev_time_s"]),
        dev_conc_wt_pct=float(st.session_state["fab_dev_conc_wt_pct"]),
        hard_bake_temp_c=float(st.session_state["fab_hard_bake_temp_c"]),
        target_aci_cd_nm=float(st.session_state["fab_target_aci_cd_nm"]),
        etch_bias_nm=float(st.session_state["fab_etch_bias_nm"]),
        min_pr_for_etch_nm=float(st.session_state["fab_min_pr_for_etch_nm"]),
    )


def _init_fab_session() -> None:
    if "fab_history" not in st.session_state or not st.session_state["fab_history"]:
        default_presets = preset_recipes("ArFi_193")
        first_name = list(default_presets.keys())[0]
        r1 = default_presets[first_name]
        _set_recipe_to_state(r1)
        c1 = run_fab_cycle(r1, cycle_id=1, label="1차 초기 불량 세팅")
        st.session_state["fab_history"] = [c1]
        st.session_state["fab_selected_cycle"] = 1
        st.session_state["fab_notice"] = ""


def _cb_load_preset() -> None:
    n_key = str(st.session_state.get("fab_preset_node", "ArFi_193"))
    presets = preset_recipes(n_key)
    p_name = str(st.session_state.get("fab_preset_name", list(presets.keys())[0]))
    if p_name not in presets:
        p_name = list(presets.keys())[0]
    r1 = presets[p_name]
    _set_recipe_to_state(r1)
    c1 = run_fab_cycle(r1, cycle_id=1, label=f"1차 ({p_name.split('(')[0].strip()})")
    st.session_state["fab_history"] = [c1]
    st.session_state["fab_selected_cycle"] = 1
    st.session_state["fab_notice"] = "새 시나리오로 1차 시뮬레이션을 초기화했습니다."


def _cb_run_current() -> None:
    history: list[CycleResult] = st.session_state["fab_history"]
    next_id = len(history) + 1
    rec = _read_recipe_from_state()
    lbl = str(st.session_state.get("fab_next_label", "")).strip() or f"{next_id}차 사용자 조정"
    res = run_fab_cycle(rec, cycle_id=next_id, label=lbl)
    history.append(res)
    st.session_state["fab_selected_cycle"] = next_id
    st.session_state["fab_next_label"] = ""
    st.session_state["fab_notice"] = f"{next_id}차 시뮬레이션 사이클을 완료하고 분석 보고서를 생성했습니다."


def _cb_apply_and_run(mode: str) -> None:
    history: list[CycleResult] = st.session_state["fab_history"]
    latest = history[-1]
    next_rec = latest.recommended_stepwise_recipe if mode == "stepwise" else latest.recommended_full_recipe
    _set_recipe_to_state(next_rec)
    next_id = len(history) + 1
    lbl = (
        f"{next_id}차 단계별 조치 적용" if mode == "stepwise" else f"{next_id}차 전체 CAPA 일괄 적용"
    )
    res = run_fab_cycle(next_rec, cycle_id=next_id, label=lbl)
    history.append(res)
    st.session_state["fab_selected_cycle"] = next_id
    st.session_state["fab_notice"] = (
        f"{latest.cycle_id}차 보고서의 권장 조치사항을 적용해 {next_id}차 시뮬레이션을 완료했습니다. "
        f"(ACI 수율: {latest.aci_yield_pct:.1f}% → {res.aci_yield_pct:.1f}%)"
    )


def _cb_apply_only(mode: str) -> None:
    history: list[CycleResult] = st.session_state["fab_history"]
    latest = history[-1]
    next_rec = latest.recommended_stepwise_recipe if mode == "stepwise" else latest.recommended_full_recipe
    _set_recipe_to_state(next_rec)
    st.session_state["fab_notice"] = (
        f"{latest.cycle_id}차 권장 조치사항을 아래 공정 세팅 패널에 채웠습니다. "
        "수치를 직접 확인·수정한 뒤 [현재 세팅으로 다음 차수 실행]을 눌러주세요."
    )


_init_fab_session()

# Clamp NA cleanly if user switched node_key manually
cur_node_key = str(st.session_state.get("fab_node_key", "ArFi_193"))
cur_node = EXPOSURE_NODES[cur_node_key]
st.session_state["fab_na"] = float(
    min(max(float(st.session_state.get("fab_na", cur_node.na_default)), cur_node.na_min), cur_node.na_max)
)

with st.sidebar:
    st.header("시나리오 & 사이클 초기화")
    preset_node = st.selectbox("노광 세대 프리셋", DUV_NODES, index=2, key="fab_preset_node", help=tip("wavelength"))
    avail_presets = list(preset_recipes(preset_node).keys())
    st.selectbox("초기 출발 시나리오", avail_presets, index=0, key="fab_preset_name")
    st.button(
        "선택 시나리오로 1차 리셋",
        icon=":material/restart_alt:",
        on_click=_cb_load_preset,
        width="stretch",
        type="secondary",
    )

render_glossary_toolbar("page7", PAGE7_TERMS)

st.title("🏭 7️⃣ 실전 Fab 공정 사이클 & 반복 수율 개선 (Run-to-Run Flow)")
st.caption(
    "전 공정(Thin Film·CMP) → 포토 8단계 → ADI 계측·데이터 분석 보고서 → 조치사항(CAPA) 반영 → 2차·3차 수율 개선 → 후 공정(Etch ACI)"
)

with st.expander("🧭 실제 반도체 Fab 포토공정 전체 흐름도 (전·후 공정 연계 & Rework 루프)", icon=":material/account_tree:", expanded=False):
    st.mermaid_chart(
        """
        flowchart LR
            PRE["1. 전 공정<br/>Thin Film 증착 & CMP 연마<br/>(하부막 n,k · 단차 Defocus)"] --> COAT["2. Track 앞단<br/>HMDS → BARC → PR 스핀코팅"]
            COAT --> BAKE1["3. Soft Bake<br/>(잔류 용매 제거)"]
            BAKE1 --> SCAN["4. Scanner 노광<br/>(파장, NA, OAI, Dose, Focus)"]
            SCAN --> BAKE2["5. PEB & Develop<br/>(산 확산 · TMAH 현상 · HB)"]
            BAKE2 --> ADI["6. ADI 계측 & 분석 보고서<br/>(CD, CDU 3σ, 반사율, 결함)"]
            ADI -- "NG: 조치사항 반영 (N+1차 재투입)" --> COAT
            ADI -- "OK: 수율 달성 출하" --> ETCH["7. 후 공정 Etch<br/>(Etch Bias 반영 최종 ACI 수율)"]
        """,
        alt="전 공정 Thin Film/CMP에서 포토 Track, Scanner, ADI 계측, 반복 재투입, 후 공정 Etch까지의 실전 Fab 공정 흐름도",
    )

render_page_concept_guide(
    "page7",
    "실전 Fab 용어 가이드 (Thin Film · CMP · ADI vs ACI · Run-to-Run APC)",
    PAGE7_TERMS,
    quick_summary=(
        "- **1차 → 2차 → 3차 체험법**: 처음 열면 `1차 초기 불량 세팅`(Al 금속 위 BARC 미적용, CMP 디싱 단차, 코팅/PEB 산포 과다)이 실행되어 있어. "
        "아래 **데이터 분석 보고서 & 향후 조치사항**을 읽은 뒤 **'권장 조치 적용 후 다음 차수 실행'** 버튼을 누르거나 수치를 직접 고쳐가며 수율이 오르는 과정을 확인해 봐!\n"
        "- **Etch Bias 연계**: 식각(Etch)에서 선폭이 `-2.0 nm` 깎인다면, 포토(ADI)는 최종 목표 `45.0 nm`보다 2nm 더 두꺼운 `47.0 nm`를 찍어야 최종 ACI 수율이 맞아."
    ),
)

if st.session_state.get("fab_notice"):
    st.success(st.session_state["fab_notice"], icon=":material/check_circle:")

history: list[CycleResult] = st.session_state["fab_history"]
latest_cycle = history[-1]
next_cycle_num = len(history) + 1

# --- Cumulative Run-to-Run Dashboard ---
st.subheader(f"📈 회차별 누적 수율 개선 트래킹 (현재 총 {len(history)}차 완료)")

summary_rows = [
    {
        "차수": f"{c.cycle_id}차",
        "시나리오/라벨": c.label,
        "최종 ACI 수율 (%)": round(c.aci_yield_pct, 1),
        "포토 ADI 수율 (%)": round(c.adi_yield_pct, 1),
        "ACI 평균 CD (nm)": round(c.aci_mean_cd_nm, 2),
        "CDU 3σ (nm)": round(c.aci_cdu_3sigma_nm, 2),
        "R_sub (%)": round(c.optics.substrate_reflectance * 100.0, 2),
        "PW Area": round(c.fem.process_window.pw_area, 0),
        "결함 위험도": round(c.defects_operating.overall_defect_risk, 1),
        "감지된 결함": ", ".join(c.defects_operating.flags) if c.defects_operating.flags else "없음",
    }
    for c in history
]
st.dataframe(
    pd.DataFrame(summary_rows),
    hide_index=True,
    width="stretch",
    alt="1차부터 현재 차수까지의 시뮬레이션 회차별 수율, CD, CDU, 반사율 및 결함 요약표",
)

if len(history) >= 1:
    fig_prog = plot_cycle_progression(history)
    fig_maps = plot_cycle_wafer_comparison(history)
    col_p1, col_p2 = st.columns([1.05, 1.15])
    with col_p1:
        st.pyplot(fig_prog, alt="시뮬레이션 차수별 ACI/ADI 수율 상승 및 CDU 3시그마, 반사율, 결함 하락 추이")
    with col_p2:
        st.pyplot(fig_maps, alt="시뮬레이션 차수별 300mm 웨이퍼 ACI CD 맵 변화 비교")
    plt.close(fig_prog)
    plt.close(fig_maps)

st.divider()

# --- Action Bar for Next Cycle ---
st.subheader(f"🔄 {latest_cycle.cycle_id}차 결과 기반 → {next_cycle_num}차 시뮬레이션 반복 개선 실행")

with st.container(border=True):
    st.markdown(
        f"**다음 차수(`{next_cycle_num}차`) 실행 방법**: "
        "아래 보고서의 **향후 필요한 조치사항(CAPA)**을 바탕으로 자동 추천을 적용하거나, "
        "직접 공정 세팅 패널 값을 수정한 뒤 실행할 수 있습니다."
    )
    b1, b2, b3, b4 = st.columns(4)
    b1.button(
        f"⚡ 단계별 조치 반영 + {next_cycle_num}차 실행",
        type="primary",
        on_click=_cb_apply_and_run,
        args=("stepwise",),
        width="stretch",
        help="핵심 병목(광학/결함 우선 → 다음 차수에 정밀 APC/산포 튜닝) 순서대로 실무형 Run-to-Run 개선을 수행합니다.",
    )
    b2.button(
        f"✨ 전체 CAPA 일괄 반영 + {next_cycle_num}차 실행",
        on_click=_cb_apply_and_run,
        args=("full",),
        width="stretch",
        help="감지된 모든 조치사항을 한 번에 적용해 다음 차수 수율을 즉시 검증합니다.",
    )
    b3.button(
        "📝 권장 수치만 세팅에 채우기",
        on_click=_cb_apply_only,
        args=("stepwise",),
        width="stretch",
        help="실행하지 않고 아래 공정 세팅 입력창 값만 업데이트해 직접 값을 조정해 볼 수 있습니다.",
    )
    b4.button(
        f"🚀 현재 수동 세팅으로 {next_cycle_num}차 실행",
        on_click=_cb_run_current,
        width="stretch",
        help="아래 4단계 공정 세팅 패널에서 사용자가 직접 맞춘 값으로 다음 시뮬레이션을 실행합니다.",
    )

# --- Sequential Recipe Editor (Actual Fab Order) ---
with st.expander(f"⚙️ 실제 공정 순서대로 세팅하기 (다음 {next_cycle_num}차 투입 레시피)", expanded=False):
    st.text_input("이번 차수 메모 라벨 (선택)", placeholder=f"예: {next_cycle_num}차 BARC 31nm + Dose 보정", key="fab_next_label")
    step_t1, step_t2, step_t3, step_t4 = st.tabs([
        "Step 1. 전 공정 (Thin Film · CMP)",
        "Step 2. 포토 코팅 (HMDS · BARC · Spin)",
        "Step 3. 노광 & 베이크 (Scanner · SB/PEB)",
        "Step 4. 현상 & 후 공정 (Develop · Etch ACI)",
    ])

    with step_t1:
        c1, c2 = st.columns(2)
        with c1:
            st.selectbox("하부막 재료 (Thin Film)", UNDERLAYERS, key="fab_underlayer_material", help=tip("thin_film"))
            st.slider("하부막 두께 (nm)", 20.0, 300.0, step=5.0, key="fab_underlayer_thickness_nm", help=tip("thin_film"))
        with c2:
            st.slider("전 공정 CMP 디싱 단차 Defocus (nm)", -90.0, 90.0, step=1.0, key="fab_cmp_dishing_defocus_nm", help=tip("cmp"))
            st.slider("CMP 단차 Focus 산포 σ (nm)", 4.0, 45.0, step=1.0, key="fab_cmp_focus_sigma_nm", help=tip("cmp"))

    with step_t2:
        c1, c2 = st.columns(2)
        with c1:
            st.selectbox("HMDS 접착 전처리", list(HMDS_OPTIONS.keys()), key="fab_hmds_label", help=tip("HMDS"))
            st.slider("BARC 두께 (nm, 0=미적용)", 0.0, 120.0, step=0.5, key="fab_barc_thickness_nm", help=tip("BARC"))
            st.slider("Spin Speed (RPM) → PR 두께 결정", 1200.0, 6500.0, step=25.0, key="fab_spin_speed_rpm", help=tip("spin_coating"))
        with c2:
            st.slider("PR 점도 Viscosity (cP)", 1.5, 10.0, step=0.5, key="fab_pr_viscosity_cp", help=tip("spin_coating"))
            st.slider("PR 토출량 Dispense Volume (mL)", 0.8, 3.5, step=0.1, key="fab_dispense_volume_ml", help=tip("spin_coating"))
            st.slider("코팅 반경 두께 편차 (nm)", 1.0, 10.0, step=0.2, key="fab_pr_radial_range_nm", help=tip("CDU"))

    with step_t3:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.selectbox("노광 세대 파장 Node", DUV_NODES, key="fab_node_key", help=tip("wavelength"))
            st.slider("NA (개구수)", float(cur_node.na_min), float(cur_node.na_max), step=0.01, key="fab_na", help=tip("NA"))
            st.selectbox("조명계 (OAI)", list(ILLUMINATION_PRESETS.keys()), key="fab_illumination", help=tip("OAI"))
            st.selectbox("패턴 타입", list(PATTERN_PRESETS.keys()), key="fab_pattern", help=tip("pattern"))
        with c2:
            st.slider("Exposure Dose (mJ/cm²)", 10.0, 55.0, step=0.1, key="fab_exposure_dose_mj_cm2", help=tip("exposure_dose"))
            st.slider("스캐너 Focus Offset (nm)", -90.0, 90.0, step=0.5, key="fab_focus_offset_nm", help=tip("cmp"))
            st.slider("스캐너 샷 Dose 산포 σ (%)", 0.3, 3.0, step=0.1, key="fab_dose_noise_sigma_pct", help=tip("CDU"))
        with c3:
            st.slider("Soft Bake Temp (°C)", 90.0, 125.0, step=0.5, key="fab_soft_bake_temp_c", help=tip("bake"))
            st.slider("PEB Temp (°C)", 105.0, 125.0, step=0.2, key="fab_peb_temp_c", help=tip("arrhenius"))
            st.slider("PEB 핫플레이트 온도 편차 (°C)", 0.2, 3.0, step=0.1, key="fab_peb_radial_range_c", help=tip("bake"))

    with step_t4:
        c1, c2 = st.columns(2)
        with c1:
            st.slider("현상 시간 Dev Time (s)", 30.0, 90.0, step=1.0, key="fab_dev_time_s", help=tip("mack"))
            st.slider("TMAH 농도 (wt%)", 2.25, 2.50, step=0.01, key="fab_dev_conc_wt_pct", help=tip("mack"))
            st.slider("Hard Bake Temp (°C)", 115.0, 145.0, step=1.0, key="fab_hard_bake_temp_c", help=tip("bake"))
        with c2:
            st.number_input("최종 목표 ACI CD (nm)", 25.0, 250.0, step=1.0, key="fab_target_aci_cd_nm", help=tip("etch_aci"))
            st.slider("후 공정 Etch Bias (nm, ACI - ADI)", -10.0, 10.0, step=0.5, key="fab_etch_bias_nm", help=tip("etch_aci"))
            st.slider("식각 버팀 최소 PR 두께 (nm)", 50.0, 300.0, step=5.0, key="fab_min_pr_for_etch_nm", help=tip("etch_aci"))

st.divider()

# --- Per-Cycle Detailed Engineering Report & Root-Cause Analysis ---
cycle_options = [f"{c.cycle_id}차 — {c.label} (ACI 수율 {c.aci_yield_pct:.1f}%)" for c in history]
default_idx = len(history) - 1
selected_str = st.selectbox(
    "📑 상세 분석 보고서 및 향후 조치사항을 확인할 시뮬레이션 차수 선택",
    cycle_options,
    index=default_idx,
    key="fab_report_selector",
)
selected_idx = cycle_options.index(selected_str)
sel_cycle = history[selected_idx]

m1, m2, m3, m4 = st.columns(4)
m1.metric("최종 ACI 수율", f"{sel_cycle.aci_yield_pct:.1f} %", delta=f"ADI {sel_cycle.adi_yield_pct:.1f}%", border=True, height="stretch")
m2.metric("ACI 평균 CD / 3σ", f"{sel_cycle.aci_mean_cd_nm:.2f} / {sel_cycle.aci_cdu_3sigma_nm:.2f} nm", delta=f"목표 {sel_cycle.target_aci_cd_nm:.1f} nm", border=True, height="stretch")
m3.metric("하부 반사율 R_sub", f"{sel_cycle.optics.substrate_reflectance*100:.2f} %", delta=f"최적 BARC {sel_cycle.optimal_barc_nm:.1f} nm", border=True, height="stretch")
m4.metric("동작점 결함 위험도", f"{sel_cycle.defects_operating.overall_defect_risk:.1f} / 100", delta=", ".join(sel_cycle.defects_operating.flags) if sel_cycle.defects_operating.flags else "결함 없음", delta_color="inverse" if sel_cycle.defects_operating.flags else "normal", border=True, height="stretch")

rep_col1, rep_col2 = st.columns([1.05, 1.0])
with rep_col1:
    fig_pareto = plot_root_cause_pareto(sel_cycle)
    st.pyplot(fig_pareto, alt=f"{sel_cycle.cycle_id}차 시뮬레이션 불량 원인별 RMS 오차 및 분산 기여율 파레토 차트")
    plt.close(fig_pareto)

with rep_col2:
    st.markdown(f"#### 🛠️ {sel_cycle.cycle_id}차 향후 필요한 조치사항 (Action Plan)")
    if not sel_cycle.action_items:
        st.success("모든 공정이 목표 스펙(수율 ≥ 95%, 반사율 < 2%, 결함 없음)을 달성해 추가 조치가 필요 없습니다.")
    else:
        for idx_a, act in enumerate(sel_cycle.action_items, start=1):
            with st.container(border=True):
                st.markdown(f"**{idx_a}. [{act.priority}] {act.stage}**")
                st.markdown(f"- **원인**: {act.issue}")
                st.markdown(f"- **조치**: {act.action}")
                st.caption(f"기대 효과: {act.expected_effect}")

with st.container(border=True):
    st.markdown(sel_cycle.report_markdown)

dl1, dl2 = st.columns(2)
with dl1:
    st.download_button(
        f"📥 {sel_cycle.cycle_id}차 분석·조치 보고서 다운로드 (.md)",
        data=sel_cycle.report_markdown.encode("utf-8"),
        file_name=f"fab_cycle_{sel_cycle.cycle_id}_report.md",
        mime="text/markdown",
        width="stretch",
    )
with dl2:
    st.download_button(
        "📥 전체 회차(1차~현재) 종합 수율 개선 보고서 (.md)",
        data=build_cumulative_summary_markdown(history).encode("utf-8"),
        file_name="fab_cumulative_yield_report.md",
        mime="text/markdown",
        width="stretch",
    )
