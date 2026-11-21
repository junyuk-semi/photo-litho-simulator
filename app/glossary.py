"""Undergraduate-friendly interactive Photolithography & AI Glossary for Streamlit pages.

Provides:
1. Structured glossary database (44 terms across 6 categories) tailored for EE undergrads.
2. Concise widget tooltip helper `tip(key)`.
3. Right-hand slide-out `@st.dialog` searchable glossary drawer callable from any page.
4. Per-page collapsible "핵심 용어 & 물리 원리 해설" guide block.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

import streamlit as st

_LOADED_MTIME: float = os.path.getmtime(__file__)


@dataclass(frozen=True)
class GlossaryTerm:
    """Single glossary entry written for undergraduate EE / semiconductor students."""

    key: str
    term: str
    category: str
    short_tip: str  # 1-2 line hover tooltip for sliders/metrics
    intuition: str  # Easy everyday / undergrad analogy
    physics: str  # Undergraduate-level physics & math explanation
    tradeoff: str  # What happens when you increase/decrease it
    where_in_app: str


GLOSSARY_LIST: List[GlossaryTerm] = [
    # --- 1. 광학 & 해상도 ---
    GlossaryTerm(
        "CD",
        "CD (Critical Dimension, 임계치수)",
        "광학·해상도",
        "웨이퍼 위에 실제로 그려진 가장 작은 패턴(선폭)의 크기(nm). 작을수록 더 미세한 반도체를 만들 수 있음.",
        "반도체 회로에서 전류가 흐르는 길(트랜지스터 게이트나 배선)의 실제 폭(nm)이야. CD가 작을수록 같은 칩 면적에 트랜지스터를 더 촘촘하게 넣을 수 있어.",
        "이론적 최소 CD는 빛의 회절 한계인 Rayleigh 공식 $CD_{min} = k_1 \\frac{\\lambda}{NA}$ 로 결정돼. 실제 공정에서는 목표 CD 대비 보통 **±10% 이내**로 들어와야 정상 소자로 인정해.",
        "CD가 너무 커지면 인접 선과 붙거나(Bridging) 소자 속도가 느려지고, 너무 작아지면 선이 끊어지거나(Pinching) PR 기둥이 쓰러져(Pattern Collapse).",
        "모든 페이지 (특히 1, 3, 4, 5페이지)",
    ),
    GlossaryTerm(
        "wavelength",
        "Wavelength (λ, 광원 파장)",
        "광학·해상도",
        "노광에 사용하는 빛의 파장(nm). 파장이 짧을수록 회절이 줄어들어 더 작은 패턴을 선명하게 그릴 수 있음.",
        "붓의 굵기라고 생각하면 돼. 굵은 붓(긴 파장)으로 작은 글씨를 쓰면 번지지만, 가는 붓(짧은 파장)은 훨씬 정밀하게 그릴 수 있어.",
        "빛은 파동이라 마스크 틈을 지나면 퍼지는 **회절(Diffraction)**이 생겨. 회절 각도는 $\\sin\\theta \\propto \\lambda / P$ 이므로 파장 $\\lambda$가 짧아질수록(i-line 365nm → KrF 248nm → ArF 193nm → EUV 13.5nm) 미세 패턴 해상도가 비약적으로 좋아져.",
        "$\\lambda$를 줄이면 CD는 작아지지만, 고에너지 광원(DUV/EUV)으로 갈수록 장비 가격이 급상승하고, 특히 EUV(13.5nm)는 공기와 유리에도 흡수돼 진공 + 반사 거울이 필요해져.",
        "1페이지(해상도), 2페이지(TMM), 5페이지(외삽 실험)",
    ),
    GlossaryTerm(
        "NA",
        "NA (Numerical Aperture, 개구수)",
        "광학·해상도",
        "렌즈가 빛을 얼마나 넓은 각도로 모을 수 있는지 나타내는 지표(NA = n·sinθ). 클수록 해상도는 좋아지지만 초점심도(DOF)가 급감함.",
        "카메라 렌즈의 '밝기(조리개 크기)'와 비슷해. 렌즈가 크고 넓게 빛을 받을수록(NA가 클수록) 미세한 디테일이 살아나지만, 초점이 맞는 범위(아웃포커싱)가 아주 얇아져.",
        "정의는 $NA = n_{fluid} \\sin\\theta_{max}$ 야. 마스크에서 회절된 ±1차 고주파 빛을 렌즈가 더 많이 받아들여야 선명한 상이 맺혀. 공기 중($n=1$)에서는 이론상 $NA < 1$ 이지만, 액침(물, $n=1.44$)을 쓰면 $NA = 1.35$ 까지 키울 수 있어.",
        "NA를 키우면 $CD \\propto 1/NA$ 로 선폭은 줄어들지만, 초점심도는 $DOF \\propto 1/NA^2$ 으로 **제곱에 반비례해 급격히 좁아지는** 치명적 트레이드오프가 발생해.",
        "1페이지(해상도/DOF 트레이드오프), 3페이지(FEM)",
    ),
    GlossaryTerm(
        "k1",
        "k1 (Process Factor, 공정 계수)",
        "광학·해상도",
        "장비(λ, NA) 외에 공정·조명·마스크 기술로 해상도를 얼마나 극한까지 끌어올렸는지 나타내는 계수. 단일 노광 물리 하한은 0.25.",
        "같은 붓과 렌즈를 써도 장인이 기술(조명 각도 조절, 마스크 보정 등)을 써서 더 얇게 그리는 '공정 난이도 점수'야. 낮을수록 고난도 첨단 공정이야.",
        "Rayleigh 식 $CD = k_1 \\frac{\\lambda}{NA}$ 에서 2광속 간섭(0차 + 1차 회절광)이 렌즈 안에 들어올 수 있는 이론적 최소 한계가 $k_1 = 0.25$ 야. 이를 넘으려면 멀티패터닝(LELE, SADP)처럼 공정을 여러 번 쪼개야 해.",
        "$k_1$을 낮추면 같은 장비로 더 작은 CD를 찍을 수 있지만, 빛의 명암비(Contrast)가 떨어지고 공정 여유도(Process Window)가 급격히 줄어들어.",
        "1페이지(해상도), 3페이지(FEM 콘트라스트)",
    ),
    GlossaryTerm(
        "DOF",
        "DOF (Depth of Focus, 초점심도) & k2",
        "광학·해상도",
        "웨이퍼가 위아래(Focus 방향)로 조금 흔들려도 패턴이 스펙(±10%) 안에 유지되는 허용 초점 범위(nm).",
        "카메라 초점이 '앞뒤로 몇 cm 벗어나도 안 흐려지는지'와 같아. 웨이퍼 표면은 미세한 단차(울퉁불퉁함)가 있어서 DOF가 넉넉해야 칩 전체가 선명하게 찍혀.",
        "소각 근사(Paraxial)에서는 $DOF = k_2 \\frac{n\\lambda}{NA^2}$, 고-NA(Immersion 등)에서는 정확한 기하광학 식 $DOF = \\frac{k_2}{2}\\frac{\\lambda}{n - \\sqrt{n^2 - NA^2}}$ 을 써. $k_2$는 레지스트·조명 조건에 따른 비례 계수야.",
        "NA를 키우면 해상도는 좋아지지만 DOF가 급격히 줄어들어. 반대로 EUV(13.5nm)는 NA가 0.33으로 낮아서 ArFi(NA 1.35)보다 해상도는 3배 좋으면서도 오히려 DOF가 더 넓은 장점이 있어!",
        "1페이지(CD vs DOF), 3페이지(Process Window)",
    ),
    GlossaryTerm(
        "immersion",
        "Immersion Lithography (액침 노광, n_fluid)",
        "광학·해상도",
        "렌즈와 웨이퍼 사이를 공기(n=1.0) 대신 초순수 물(n=1.44)로 채워 NA를 1.35까지 높이고 DOF도 늘리는 기술.",
        "물속에 빨대를 넣으면 꺾여 보이듯(굴절), 렌즈 아래에 물을 채우면 빛이 더 급격히 꺾여 들어가서 공기 중엔 못 잡던 빛까지 모아 해상도와 초점심도를 동시에 개선해.",
        "공기에서는 $\\sin\\theta \\le 1$ 이므로 $NA < 1$ 이 한계지만, 193nm에서 물의 굴절률 $n_{fluid}=1.44$ 를 이용하면 $NA = n\\sin\\theta$ 를 최대 1.35까지 확장할 수 있어. 또한 같은 NA에서 $DOF$가 약 $n_{fluid}$배(~44%) 커져.",
        "ArF 193nm 장비의 수명을 크게 연장해 40nm 이하 패터닝을 가능하게 했지만, 물방울 잔류(Watermark) 결함과 고속 스캔 시 기포 제어가 까다로워져.",
        "1페이지(Dry vs Immersion 비교), 2페이지(Ambient 매질)",
    ),
    GlossaryTerm(
        "OAI",
        "Illumination / OAI (Off-Axis Illumination, 사입사 조명)",
        "광학·해상도",
        "빛을 수직이 아닌 비스듬한 각도(Annular, Dipole, Quadrupole)로 쏴서 해상도와 Dense 패턴의 DOF를 높이는 조명 기술.",
        "가로등 불빛을 똑바로 내리쬐는 대신, 양옆에서 비스듬히 비추면 좁은 틈의 그림자가 훨씬 또렷해지는 원리야.",
        "수직 조명(Conventional)은 0차·+1차·-1차 회절광이 대칭으로 퍼져 고밀도 패턴에서 ±1차가 렌즈 밖으로 잘려나가. 빛을 비스듬히 쏘면(OAI) 0차와 한쪽 1차 회절광만 렌즈 양끝으로 통과시켜 2광속 간섭을 유지하므로 유효 $k_1$이 줄고 Dense DOF가 커져.",
        "Dipole/Annular는 1:1 촘촘한(Dense) 패턴의 해상도와 DOF를 크게 높여주지만, 고립된 선(Isolated Line)에서는 오히려 DOF가 줄어드는 단점이 있어.",
        "1페이지(OAI 선택), 3페이지(FEM), 5페이지(최적화)",
    ),
    GlossaryTerm(
        "pattern",
        "Pattern Type (Dense 1:1 vs Isolated Line) & Pitch",
        "광학·해상도",
        "선폭과 간격이 1:1로 빽빽한 반복 패턴(Dense)과 혼자 떨어져 있는 패턴(Isolated). 피치(Pitch)는 선폭+간격의 주기.",
        "아파트가 다닥다닥 붙어있는 단지(Dense)와 들판에 홀로 선 단독주택(Isolated)의 차이야. 빛의 회절 간섭 양상이 완전히 달라져.",
        "주기 $P$가 작은 Dense 패턴은 회절 차수가 이산적으로 크게 벌어지고, Isolated 패턴은 연속 스펙트럼을 가져. 그래서 Focus가 틀어질 때 CD가 변하는 곡선(Bossung 곡선)이 Dense와 Iso에서 서로 반대 방향(Smile vs Frown)으로 휘어져.",
        "실제 칩에는 Dense와 Iso 패턴이 함께 존재하므로, 둘의 공통 Process Window를 맞추기 위해 OPC(광근접보정)나 조명 최적화가 필수야.",
        "1페이지, 3페이지(FEM Bossung 곡선 비교)",
    ),
    GlossaryTerm(
        "exposure_dose",
        "Exposure Dose / Light Intensity / Exposure Time",
        "광학·해상도",
        "웨이퍼 단위 면적당 조사된 빛 에너지(mJ/cm²). Dose = 광도(mW/cm²) × 노광시간(s). Positive PR에서는 Dose↑ → Line CD↓.",
        "햇볕에 피부가 타는 정도(에너지) = 햇빛 세기(광도) × 쬔 시간(노광시간)과 똑같아.",
        "$E = I_0 \\times t_{exp}$. Positive PR은 빛을 많이 받을수록 화학 반응(산 생성/분해)이 많이 일어나 현상액에 더 넓게 녹아 없어져. 따라서 노광량 $E$를 높이면 남아있는 PR 선폭(Line CD)은 좁아져.",
        "Dose가 너무 크면 선이 과도하게 얇아져 끊어지거나(Pinching) 쓰러지고, 너무 작으면 PR이 덜 녹아 잔막(Scumming)이 남아.",
        "1페이지(노광에너지 계산기), 3페이지(FEM y축)",
    ),
    GlossaryTerm(
        "pr_tone",
        "Positive PR vs Negative PR (감광액 극성)",
        "광학·해상도",
        "빛을 받은 부분이 현상 후 녹아 없어지면 Positive PR, 반대로 남으면 Negative PR. 본 시뮬레이터는 첨단 공정 표준인 Positive PR 기준.",
        "도장 찍을 때 빛 받은 곳을 파내는 방식이 Positive, 빛 받은 곳만 굳혀 남기는 방식이 Negative야.",
        "Positive PR은 해상도가 우수하고 핀홀이 적어 미세 반도체 공정의 표준이야(강의자료 7주차 Slide 6, 10). Dose가 증가할수록 빛 받은 영역이 넓어져 남는 PR 선폭(Line CD)이 단조 감소해.",
        "Positive PR은 산화막 접착력이 상대적으로 약해서 코팅 전 HMDS 표면 처리가 꼭 필요해.",
        "홈 화면, 3페이지(Bossung 기울기 부호)",
    ),
    # --- 2. 박막 간섭 & BARC ---
    GlossaryTerm(
        "nk",
        "Refractive Index (n) & Extinction Coefficient (k)",
        "박막간섭·BARC",
        "복소 굴절률 ñ = n + ik. 실수부 n은 매질 속 빛의 속도와 위상(간섭 주기)을, 허수부 k는 빛이 흡수돼 줄어드는 정도를 결정.",
        "n은 빛을 얼마나 느리게·많이 꺾이게 하는지(투명 유리의 성질), k는 선글라스처럼 빛을 얼마나 강하게 흡수하는지(불투명도)를 뜻해.",
        "매질 내 파수 $k_{wave} = \\frac{2\\pi}{\\lambda}(n + ik)$ 이므로 전기장은 $e^{i\\frac{2\\pi n}{\\lambda}z} e^{-\\frac{2\\pi k}{\\lambda}z}$ 로 진행해. 실수부 $n$은 정상파 주기 $\\lambda/(2n)$을, 허수부 $k$는 흡수 감쇠를 지배해.",
        "PR은 빛이 바닥까지 닿아야 하므로 $k$가 매우 작고($\\approx 0.02$), BARC는 반사광을 먹어 없애야 하므로 적당히 큰 $k$($\\approx 0.45$)를 설계해.",
        "2페이지(사이드바 PR/BARC n, k 조절)",
    ),
    GlossaryTerm(
        "alpha",
        "Absorption Coefficient (α, Beer-Lambert 흡수계수)",
        "박막간섭·BARC",
        "빛이 매질 속을 1 μm 통과할 때 강도가 지수적으로 감쇠하는 비율(α = 4πk / λ).",
        "탁한 물속 깊이 들어갈수록 어두워지는 속도를 수치로 나타낸 거야.",
        "Beer-Lambert 법칙 $I(z) = I_0 e^{-\\alpha z}$ 에서 흡수계수는 $\\alpha = \\frac{4\\pi k}{\\lambda}$ 로 소광계수 $k$에 비례해.",
        "$\\alpha$가 너무 크면 PR 윗면만 과노광되고 바닥은 빛이 안 닿아 사다리꼴 프로파일(미현상)이 생기고, 너무 작으면 감광 반응 효율이 떨어져.",
        "2페이지(광학 요약 캡션)",
    ),
    GlossaryTerm(
        "tmm",
        "Fresnel 방정식 & 2×2 TMM / S-Matrix (다층 박막 계산)",
        "박막간섭·BARC",
        "공기/물–PR–BARC–하부막–Si 여러 층의 경계면 반사·투과와 위상 간섭을 정확히 푸는 전자기학 행렬 알고리즘.",
        "비눗방울 표면에서 무지개색이 보이는 얇은 막 빛 간섭을, 반도체처럼 층이 4~5개 겹친 구조에서도 오차 없이 계산하는 공식이야.",
        "각 계면의 Fresnel 반사계수 $r_{ij} = \\frac{\\tilde{n}_i - \\tilde{n}_j}{\\tilde{n}_i + \\tilde{n}_j}$ 와 층 내부 위상 전파 $e^{i\\frac{2\\pi}{\\lambda}\\tilde{n}_j d_j}$ 를 행렬곱으로 연결해. 본 시뮬레이터는 두꺼운 금속층에서도 수치 발산이 없는 **Redheffer S-Matrix(TMM과 수학적 100% 등가)**를 사용해.",
        "1D 평탄 박막에서는 맥스웰 방정식의 엄밀해지만, 실제 소자의 3D 단차 경사면 반사는 별도 3D EM 시뮬레이션이 필요해.",
        "2페이지(전체 광학 계산 엔진)",
    ),
    GlossaryTerm(
        "RTA",
        "Reflectance (R) / Transmittance (T) / Absorptance (A) & R_sub",
        "박막간섭·BARC",
        "입사광 중 반사(R), 기판 투과(T), 박막 흡수(A) 비율(R+T+A=1). R_sub는 PR 바닥에서 하부막이 PR 쪽으로 되돌려 보내는 반사율.",
        "PR로 들어간 빛이 바닥 거울(Si, 알루미늄 등)에 맞아 얼마나 되튀어 올라오는지가 R_sub야.",
        "에너지 보존 법칙에 의해 항상 $R + T + A = 1$ 이 성립해. 공정 엔지니어가 가장 신경 쓰는 값은 PR 바닥 계면 반사율 $R_{sub}$ 이며, 보통 **BARC를 써서 $R_{sub} < 2\\%$ 이하**로 억제하는 것이 목표야.",
        "$R_{sub}$가 크면 PR 내부에 강한 정상파(Standing Wave)가 생겨 측벽이 물결치고 CD 제어가 망가져.",
        "2페이지(KPI 카드), 3페이지(Notching 판정)",
    ),
    GlossaryTerm(
        "standing_wave",
        "Standing Wave (정상파) & 주기 λ/(2n)",
        "박막간섭·BARC",
        "위에서 내려오는 입사광과 바닥에서 반사돼 올라오는 빛이 겹쳐 PR 두께 방향으로 밝고 어두운 줄무늬가 생기는 현상.",
        "줄넘기 줄을 벽에 묶고 흔들면 제자리에서 출렁이는 파도(정상파)가 생기듯, PR 안에서 빛의 세기가 위아래로 강-약-강-약 반복돼.",
        "입사파 $E^+(z)$와 반사파 $E^-(z)$가 보강/상쇄 간섭을 일으켜 $I(z) = |E^+(z)+E^-(z)|^2$ 가 깊이 $z$에 따라 주기 $\\Lambda = \\frac{\\lambda}{2n_{PR}}$ (193nm 기준 약 57nm)로 진동해(9주차 Slide 18~19).",
        "어두운 마디(Node) 부분은 빛이 부족해 덜 녹으면서 PR 측벽이 계단처럼 울퉁불퉁해져. 해결책은 **BARC 적용**과 **PEB(산 확산으로 평탄화)**야.",
        "2페이지(PR 내부 광강도 I(z) 그래프)",
    ),
    GlossaryTerm(
        "SWR",
        "SWR (Standing Wave Ratio, 정상파 비)",
        "박막간섭·BARC",
        "PR 내부 정상파의 최대 광강도 / 최소 광강도 비율(I_max / I_min). 1.0이면 반사 없음(이상적), 클수록 측벽 물결이 심함.",
        "파도의 가장 높은 마루와 가장 낮은 골의 차이 비율이야. 잔잔한 호수면 1.0, 거친 파도면 숫자가 커져.",
        "하부 반사가 0이면 $I(z)$는 Beer-Lambert 감쇠만 남아 detrended $SWR = 1.0$ 이 돼. 알루미늄(Al)처럼 반사가 큰 금속 위에서 BARC가 없으면 SWR이 3~10 이상으로 치솟아.",
        "본 시뮬레이터에서는 $SWR > 2.0$ 또는 $R_{sub} > 15\\%$ 일 때 Reflective Notching 결함 위험을 경고해.",
        "2페이지(KPI 카드), 3페이지(결함 진단)",
    ),
    GlossaryTerm(
        "swing_curve",
        "Swing Curve (스윙 커브)",
        "박막간섭·BARC",
        "PR 두께가 조금만 변해도 반사율과 PR 내부 흡수 광량이 주기적으로 출렁이는 현상(주기 λ/2n).",
        "박막 간섭 때문에 PR 두께가 10nm만 두꺼워지거나 얇아져도 어떤 곳은 빛을 많이 먹고 어떤 곳은 반사해 버리는 '롤러코스터 곡선'이야.",
        "웨이퍼 표면은 코팅 편차나 하부 단차 때문에 PR 두께가 완전히 균일할 수 없어. Swing 진폭이 크면 불과 수 nm의 PR 두께 차이가 큰 유효 노광량(Dose) 차이로 이어져 CD Uniformity가 크게 나빠져.",
        "BARC를 최적 두께로 깔면 Swing Curve가 납작하게 펴져서, PR 두께가 조금 흔들려도 CD가 안정적으로 유지돼.",
        "2페이지(하단 좌측 Swing Curve 그래프)",
    ),
    GlossaryTerm(
        "BARC",
        "BARC (Bottom Anti-Reflective Coating, 하부 반사방지막)",
        "박막간섭·BARC",
        "PR과 하부 기판 사이에 까는 얇은 광학 막. 반사광을 흡수하고 상쇄간섭을 일으켜 기판 반사율(R_sub)과 Swing을 극소화함.",
        "안경 렌즈의 '빛 반사 방지 코팅'을 웨이퍼 PR 밑바닥에 깐 거라고 보면 돼.",
        "두께가 대략 $d_{BARC} \\approx \\frac{\\lambda}{4n_{BARC}}$ (1차 극소점) 부근일 때 BARC 윗면과 아랫면 반사파의 위상차가 $180^\\circ$가 되어 **상쇄간섭**이 일어나고, 동시에 BARC의 $k$ 값이 빛을 흡수해 $R_{sub}$를 1~2% 미만으로 줄여줘.",
        "BARC 두께를 잘못 맞추면(예: 반파장 $\\lambda/2n$ 근처) 오히려 보강간섭으로 반사가 커질 수 있어. 그래서 TMM 최적화가 중요해!",
        "2페이지(BARC 최적화), 3페이지(FEM), 4페이지(CDU 개선)",
    ),
    GlossaryTerm(
        "underlayer",
        "Underlayer (하부막 — Bare Si, SiO₂, Poly-Si, Al Metal)",
        "박막간섭·BARC",
        "PR 바로 아래에 놓인 실제 반도체 막질. 재료마다 굴절률(n, k)과 반사율이 달라 필요한 노광 에너지와 BARC 조건이 달라짐.",
        "그림을 그리는 도화지 재질이야. 무광 종이(SiO₂)와 거울 같은 은박지(Al 금속) 위에서 빛 반사가 완전히 다르지(9주차 Slide 15, 20).",
        "193nm에서 SiO₂($k=0$)는 투명하고 반사가 적은 반면, Al 금속($n=0.11, k=2.20$)은 반사율이 매우 높아 BARC 없이 노광하면 심한 정상파와 Notching이 발생해.",
        "하부막이 바뀔 때마다(Gate Poly, Oxide Contact, Metal 배선 공정) 그 막질의 $(n, k)$에 맞는 최적 BARC 두께를 새로 찾아야 해.",
        "2, 3, 4, 5페이지 하부막 선택 메뉴",
    ),
    GlossaryTerm(
        "eta_abs",
        "η_abs (Effective Absorbed Dose Factor, 유효 흡수 효율)",
        "박막간섭·BARC",
        "다층 박막 간섭으로 인해 PR 내부가 실제로 받는 평균 광강도 비율. FEM에서 유효 노광량 E_eff = Dose × η_abs로 직결됨.",
        "장비에서 28 mJ/cm²를 쐈더라도, 바닥 반사·간섭 때문에 PR이 실제로 '체감하는 빛의 양'이 몇 배인지를 나타내는 환산 계수야.",
        "반사가 전혀 없는 이상적 기준 스택의 평균 광강도 대비 현재 스택의 평균 광강도 $\\eta_{abs} = \\bar{I}_{PR} / \\bar{I}_{ref}$ 로 정의해. 본 시뮬레이터에서 **3단계 광학(TMM)과 4단계 FEM을 물리적으로 연결하는 핵심 다리**야.",
        "BARC 없이 PR 두께가 흔들리면 $\\eta_{abs}$가 크게 요동쳐서 FEM의 Dose 축이 좌우로 밀리고 웨이퍼 CDU가 악화돼.",
        "2페이지(KPI), 3페이지(Bossung 제목), 4~5페이지(데이터·ML 피처)",
    ),
    # --- 3. FEM, Process Window & 결함 ---
    GlossaryTerm(
        "FEM",
        "FEM (Focus–Exposure Matrix)",
        "노광·FEM·결함",
        "웨이퍼 한 장에서 가로축은 Focus, 세로축은 Exposure Dose를 격자처럼 바꿔가며 노광해 최적 공정 조건을 찾는 핵심 실험.",
        "신규 레시피를 잡을 때 웨이퍼 바둑판 칸마다 초점과 노광량을 조금씩 다르게 찍어보고, 가장 예쁘고 안정적으로 나온 구역을 찾는 '정답 찾기 실험'이야.",
        "2차원 $(Focus, Dose)$ 평면 위에서 각 조건의 $CD(E, \\Delta z)$ 를 측정/시뮬레이션해 등고선(Contour)과 히트맵으로 표현해. 포토 공정기술 엔지니어가 실무에서 가장 자주 보는 데이터야.",
        "FEM 중심(Best Focus, Best Dose)에서 멀어질수록 CD가 목표치 ±10%를 벗어나 불량이 발생해.",
        "3페이지(FEM Contour & Heatmap)",
    ),
    GlossaryTerm(
        "bossung",
        "Bossung Plot (보성 곡선 — Smile/Frown & Iso-focal)",
        "노광·FEM·결함",
        "FEM 데이터를 Focus(x축)에 따른 CD(y축) 곡선 묶음으로 그린 그래프. Dose별로 포물선처럼 휘며, 평평해지는 지점이 Iso-focal.",
        "초점이 흔들릴 때 선폭이 위로 휘는지(웃는 입 모양 Smile), 아래로 휘는지(찡그린 입 모양 Frown)를 한눈에 보여주는 그래프야.",
        "낮은 Dose와 높은 Dose에서 초점 이탈 시 CD 변화 곡률의 부호가 뒤집히며, 그 경계에서 Focus 변화에 거의 둔감한 **Iso-focal Dose**가 존재해. Dense와 Iso 패턴은 기본 곡률 부호가 달라 곡선 모양이 다르게 나타나.",
        "Iso-focal 부근에서 목표 CD가 나오도록 공정 조건을 맞추면 초점이 흔들려도 CD가 잘 안 변해서 넓은 DOF를 얻을 수 있어.",
        "3페이지(우측 Bossung Plot)",
    ),
    GlossaryTerm(
        "contrast",
        "Aerial Image Contrast & NILS",
        "노광·FEM·결함",
        "마스크를 통과해 PR 위에 맺힌 빛의 밝은 부분(I_max)과 어두운 부분(I_min)의 대비. 초점이 틀어지면 급격히 흐려짐.",
        "빔프로젝터 초점이 잘 맞으면 글씨 경계가 칼처럼 선명(Contrast 높음)하지만, 초점이 어긋나면 뿌옇게 번지는(Contrast 낮음) 것과 같아.",
        "명암비 $C = \\frac{I_{max} - I_{min}}{I_{max} + I_{min}}$ 이고, 경계면 기울기를 정규화한 값이 **NILS**(Normalized Image Log-Slope)야. Contrast/NILS가 높을수록 Dose 변화에 덜 민감하고 패턴 경계가 깨끗해.",
        "Defocus $|\\Delta z|$가 커지면 $C(\\Delta z)$가 급감해 경계가 무너지고 결국 Bridging이나 Pinching 결함이 생겨.",
        "3페이지(Bossung 모델 & Bridging 결함 기준)",
    ),
    GlossaryTerm(
        "PW",
        "Process Window (PW) & 최대 내접 직사각형",
        "노광·FEM·결함",
        "목표 CD ±10% 스펙을 만족하는 (Focus, Dose) 안전 영역. 그 안에 꽉 차게 들어가는 가장 큰 직사각형으로 공정 여유도를 정량화함.",
        "운전할 때 차선(±10% CD)을 벗어나지 않는 '안전 주행 구역'의 넓이야. 구역이 넓을수록 장비가 약간 흔들려도 불량이 안 나.",
        "실제 양산에서는 Focus와 Dose가 동시에 흔들리므로, 허용 영역 내부에 **최대 면적 직사각형**을 내접시켜 가로 길이(**PW DOF**, nm)와 세로 비율(**PW EL%**)의 곱(`PW Area = DOF × EL%`)을 공정 강건성 지표로 써.",
        "목표 CD만 딱 맞추는 조건보다, **PW Area가 최대가 되는 조건**을 고르는 게 진짜 공정 최적화야.",
        "3페이지(노란색 사각형), 5페이지(최적화 목적함수)",
    ),
    GlossaryTerm(
        "EL",
        "EL% (Exposure Latitude, 노광 여유도)",
        "노광·FEM·결함",
        "목표 CD ±10%를 유지하면서 허용되는 Exposure Dose 변동 폭의 백분율(%). 보통 양산에서 5~10% 이상을 요구함.",
        "노광량이 목표치에서 몇 % 정도 삐끗해도 괜찮은지 나타내는 'Dose 쪽 쿠션'이야.",
        "$EL(\\%) = \\frac{E_{max} - E_{min}}{E_{center}} \\times 100$. Aerial Image의 기울기(NILS)가 가파를수록 EL%가 넓어져.",
        "EL%와 DOF는 서로 트레이드오프가 있어서, EL을 크게 잡으면 허용 DOF가 줄어들고 DOF를 넓히면 EL이 좁아져.",
        "3페이지(PW KPI), 5페이지(최적 레시피 표)",
    ),
    GlossaryTerm(
        "collapse",
        "Pattern Collapse (패턴 붕괴) & Aspect Ratio (AR)",
        "노광·FEM·결함",
        "PR 선폭(CD) 대비 높이(PR 두께) 비율인 종횡비(AR = d_PR / CD)가 너무 크면, 현상·건조 시 모세관력에 의해 PR 기둥이 쓰러지는 결함.",
        "가늘고 키가 너무 큰 도미노 블록에 물을 묻혔다 말리면 표면장력 때문에 옆으로 픽 쓰러지는 현상이야.",
        "종횡비 $AR = d_{PR} / CD$. 보통 $AR > 3.0$ (HMDS 표면처리가 없으면 접착력이 약해 $AR > 2.2$)을 넘어가면 린스 건조 시 모세관력(Capillary force)을 버티지 못하고 패턴이 무너져.",
        "미세 CD로 갈수록 PR 두께도 같이 얇게 줄여야 하지만, 너무 얇으면 다음 식각(Etch) 공정에서 마스크가 다 깎여버리는 트레이드오프가 있어.",
        "3페이지(결함 진단 카드)",
    ),
    GlossaryTerm(
        "scumming",
        "Scumming (스컴 / 미현상 잔막)",
        "노광·FEM·결함",
        "노광량이 부족하거나 Soft Bake가 과도해, 녹아 없어져야 할 Positive PR 바닥에 찌꺼기가 남는 결함.",
        "설거지할 때 세제가 약하거나 기름이 너무 말라붙어 그릇 바닥에 얼룩이 덜 씻기고 남은 상태야(9주차 Slide 17).",
        "유효 노광량 $E_{eff}$가 부족하거나 과도한 Soft Bake로 PR이 열경화되면 현상액(TMAH)에 완전히 용해되지 못하고 스페이스 바닥에 잔막(Scum)이 남아 식각을 막아버려.",
        "Dose를 높이거나 Soft Bake 온도를 적정 수준으로 낮추고 현상 시간을 조절해 해결해.",
        "3페이지(결함 진단 카드)",
    ),
    GlossaryTerm(
        "bridging",
        "Bridging / Pinching (브리지 · 핀칭)",
        "노광·FEM·결함",
        "이웃한 패턴이 서로 붙어버리거나(Bridging), 과노광·초점 이탈로 선폭이 너무 가늘어져 끊어지는(Pinching) 치명적 결함.",
        "회로 배선이 옆 줄과 합선(단락)되거나, 중간이 뚝 끊어져(단선) 전기가 안 통하는 치명적 불량이야.",
        "Positive PR에서 과노광으로 Line CD가 목표 대비 75% 미만으로 얇아지거나, 극심한 Defocus로 Aerial Image Contrast가 0.25 미만으로 무너지면 발생 위험이 급증해.",
        "적정 Focus/Dose 중앙 유지와 OAI 조명을 통한 Contrast 확보로 예방해.",
        "3페이지(결함 진단 카드)",
    ),
    GlossaryTerm(
        "notching",
        "Reflective Notching (반사 노칭)",
        "노광·FEM·결함",
        "하부막(특히 Al 금속 등)의 높은 반사광이 PR 측면으로 파고들어 패턴 옆구리가 패이거나 울퉁불퉁해지는 결함.",
        "바닥이 거울처럼 반짝여서 원치 않는 옆구리 부분까지 빛을 쏴버려 패턴이 파먹히는 현상이야(9주차 Slide 20).",
        "기판 반사율 $R_{sub} > 15\\%$ 또는 정상파 비 $SWR > 2.0$ 인 고반사 조건에서 강하게 나타나. 실제 3D 단차(Al 경사면 $60^\\circ\\sim70^\\circ$)에서는 훨씬 심각해져.",
        "최적 두께의 **BARC**를 삽입해 $R_{sub}$를 2% 미만으로 낮추는 것이 가장 효과적인 해결책이야.",
        "2페이지(BARC 비교), 3페이지(결함 진단 카드)",
    ),
    # --- 4. Tier 2 코팅·베이크·현상 & CDU ---
    GlossaryTerm(
        "spin_coating",
        "Spin Coating & Meyerhofer 모델 (RPM, Viscosity)",
        "코팅·베이크·현상",
        "웨이퍼를 고속 회전(RPM)시켜 원심력과 용매 증발로 균일한 PR 박막을 입히는 공정. 두께는 점도^(1/3)·속도^(-1/2)에 비례.",
        "물감을 접시 가운데 떨어뜨리고 빠르게 돌리면 얇게 펴지고, 꿀처럼 끈적(고점도)하거나 천천히 돌리면 두껍게 발리는 원리야(7주차 Slide 15~17).",
        "Emslie-Bonner-Peck 유체역학에 용매 증발을 결합한 **Meyerhofer 모델**은 최종 건조 두께가 $d_{PR} \\propto \\eta^{1/3} \\omega^{-1/2}$ 로 스케일링됨을 보여줘. 속도를 2배 올려도 두께는 $1/\\sqrt{2}$(약 0.71배)만 줄어들어.",
        "회전 속도(RPM)와 토출량(Dispense Volume), 가속도(Spin Accel)가 부적절하면 웨이퍼 중심과 가장자리 두께 차이(Radial Bow)와 Edge Bead가 커져 CDU가 나빠져.",
        "4페이지(스핀코팅 두께 추정 & 웨이퍼 CDU)",
    ),
    GlossaryTerm(
        "HMDS",
        "HMDS (Hexamethyldisilazane 표면 처리)",
        "코팅·베이크·현상",
        "친수성 SiO₂ 웨이퍼 표면을 소수성으로 바꿔 Positive PR이 잘 달라붙게 만드는 전처리 공정.",
        "유리창에 물기(친수성)가 있으면 스티커가 자꾸 떨어지니까, 접착 프라이머를 한 번 발라주는 과정이야(7주차 Slide 12~14).",
        "웨이퍼 표면의 실라놀기(-OH)를 HMDS와 반응시켜 소수성 메틸기(-CH₃)로 치환해. 기상(Vapor) 처리가 스핀(Spin) 처리보다 균일하고 접착력이 우수해.",
        "HMDS를 생략하면 현상·린스 중 PR이 웨이퍼에서 들뜨거나 낮은 Aspect Ratio에서도 쉽게 쓰러져(Pattern Collapse).",
        "3페이지(Tier 2 사이드바)",
    ),
    GlossaryTerm(
        "bake",
        "Soft Bake (SB) / PEB / Hard Bake (HB)",
        "코팅·베이크·현상",
        "코팅 후 용매 제거(SB), 노광 후 산 확산·정상파 완화(PEB), 현상 후 내식각성 강화(HB)를 위한 3단계 열처리.",
        "빵 반죽을 굽듯(Bake), PR 코팅 후 말리고(SB), 빛 쬔 뒤 화학반응을 숙성시키고(PEB), 다 깎은 뒤 단단하게 굳히는(HB) 과정이야.",
        "**Soft Bake**(90~115°C)는 용매를 날려 막을 안정화해. **PEB**(105~125°C)는 노광으로 생성된 산(Acid)을 확산시켜 화학 증폭 반응을 일으키고 정상파 측벽 물결을 부드럽게 펴줘(9주차 Slide 19). **Hard Bake**(>135°C 주의)는 내식각성을 높이지만 과열 시 PR이 녹아 흘러내려(Thermal Flow, 7주차 Slide 22).",
        "특히 **PEB 온도**는 1°C만 틀어져도 CD가 1~2nm씩 변할 만큼 민감해서, 핫플레이트 온도 균일도가 웨이퍼 CDU의 핵심 변수야.",
        "3페이지(Tier 2 보정), 4페이지(PEB 핫플레이트 온도 편차)",
    ),
    GlossaryTerm(
        "arrhenius",
        "Arrhenius 산 확산 (PEB Acid Diffusion Length, L_diff)",
        "코팅·베이크·현상",
        "PEB 온도가 높아질수록 화학증폭형 레지스트(CAR) 내 산 분자의 확산 속도가 지수적으로 빨라지는 물리 법칙.",
        "따뜻한 물에 잉크를 떨어뜨리면 찬물보다 훨씬 빠르게 퍼지는 것과 같아.",
        "확산 계수 $D(T) = D_0 \\exp(-E_a / k_B T)$ 를 따르며, 확산 거리는 $L_{diff} = \\sqrt{2 D(T) t_{PEB}}$ 야. 온도가 조금만 올라도 지수 함수 때문에 확산 거리가 급격히 늘어 Positive PR 선폭이 좁아져.",
        "적당한 확산은 정상파를 없애주지만, 과도한 확산은 패턴 경계를 뭉개 콘트라스트를 떨어뜨려.",
        "3페이지(PEB 온도 조절), 4페이지(웨이퍼 CDU)",
    ),
    GlossaryTerm(
        "mack",
        "Mack Dissolution Model (현상 속도 모델) & TMAH",
        "코팅·베이크·현상",
        "노광 후 남은 감광억제제 농도(M)에 따라 현상액(TMAH 2.38 wt%)이 PR을 녹이는 속도 R(M)을 나타내는 비선형 수식.",
        "빛을 덜 받은 부분은 거의 안 녹고, 임계치 이상 빛을 받은 부분만 갑자기 확 녹아내리는 '스위치 같은 용해 특성'을 수학으로 표현한 거야.",
        "Chris Mack 모델: $R(M) = R_{min} + (R_{max} - R_{min})\\frac{(a+1)(1-M)^n}{a + (1-M)^n}$. 반응 차수 $n$이 클수록 계단처럼 급격하게 녹아 패턴 측벽이 수직에 가까워져.",
        "현상 시간($t_{dev}$), TMAH 농도(표준 2.38 wt%), 온도가 높아질수록 PR이 더 많이 녹아 Line CD가 줄어들어.",
        "3페이지(Tier 2 현상 변수), 5페이지(ML 입력 변수)",
    ),
    GlossaryTerm(
        "CDU",
        "CDU (CD Uniformity, 3σ) & 300mm Wafer Map",
        "코팅·베이크·현상",
        "300mm 웨이퍼 전체에 찍힌 수백 개 칩의 CD가 얼마나 고르게 나왔는지 나타내는 산포 지표(표준편차 × 3). 작을수록 우수.",
        "피자 한 판(300mm 웨이퍼)에서 가운데 조각과 테두리 조각의 토핑 크기가 얼마나 똑같은지 보는 품질 성적표야.",
        "정규분포에서 $\\text{Mean} \\pm 3\\sigma$ 범위가 전체의 99.7%를 포함하므로 반도체 업계에서는 **$3\\sigma$ (nm 또는 목표 CD 대비 %)**를 표준 균일도 지표로 써. 웨이퍼 반경 방향 코팅 두께 편차 + PEB 핫플레이트 온도 구배 + 샷별 Focus/Dose 산포가 복합적으로 합쳐져 나타나.",
        "같은 PR 두께 편차라도 BARC를 깔아 Swing을 줄이면 웨이퍼 CDU(3σ)가 눈에 띄게 개선돼.",
        "4페이지(300mm 웨이퍼 CDU 맵)",
    ),
    # --- 5. 데이터 분석 & DOE ---
    GlossaryTerm(
        "LHS",
        "LHS (Latin Hypercube Sampling) & 가상 Fab 데이터",
        "데이터·DOE·통계",
        "다차원 공정 변수 공간을 빈틈없이 고르게 탐색하는 스마트 샘플링 기법. 본 시뮬레이터는 LHS + 현실 노이즈로 가상 데이터를 생성.",
        "무작위로 주사위를 던지면 어떤 구역은 몰리고 어떤 구역은 비는데, LHS는 체스판의 모든 행과 열에 하나씩 겹치지 않게 배치하듯 골고루 실험점을 뽑아줘.",
        "9개의 연속 공정 변수를 균일하게 커버한 뒤 물리 엔진(TMM+Bossung+Tier 2)을 통과시키고, 실제 Fab의 미관측 PEB 드리프트와 CD-SEM 계측 노이즈를 더해 가상 양산 데이터를 만들어.",
        "단순 난수보다 적은 샘플 수로도 회귀·ML 모델 학습과 공간 탐색 효율이 훨씬 높아져.",
        "4페이지(데이터 생성), 5페이지(ML 학습 데이터)",
    ),
    GlossaryTerm(
        "correlation",
        "Pearson Correlation (피어슨 상관계수 r)",
        "데이터·DOE·통계",
        "두 변수 사이의 직선적 관계 강도(-1 ~ +1). Positive PR에서 Dose와 Line CD는 강한 음(-)의 상관관계를 보임.",
        "한 변수가 커질 때 다른 변수가 같이 커지면 +1, 반대로 줄어들면 -1, 아무 직선 관계가 없으면 0이야.",
        "$r = \\frac{\\text{Cov}(X, Y)}{\\sigma_X \\sigma_Y}$. 주의할 점은 **Focus처럼 좌우 대칭인 포물선($\\Delta z^2$) 관계는 직선 상관계수 r이 0에 가깝게 나올 수 있다**는 거야! 그래서 `abs_focus_nm`이나 비선형 분석(DOE/SHAP)을 함께 봐야 해.",
        "상관관계가 높다고 인과관계가 자동 증명되지는 않으며, 비선형 간섭 효과는 놓칠 수 있어.",
        "4페이지(상관관계 히트맵)",
    ),
    GlossaryTerm(
        "OLS",
        "OLS 다중선형회귀 & Standardized Beta (표준화 회귀계수)",
        "데이터·DOE·통계",
        "여러 공정 변수가 CD에 미치는 선형 영향력을 동시에 추정하는 통계 모델. 표준화 계수(|std_beta|)로 단위가 다른 변수들의 영향력을 공정하게 비교.",
        "Dose(mJ/cm²)와 PEB 온도(°C)는 단위가 달라서 그냥 기울기만 비교하면 불공평해. 모든 변수를 표준편차 1 단위로 통일해 '누가 CD를 제일 많이 흔드는지' 순위를 매긴 게 Standardized Beta야.",
        "최소제곱법으로 $y = \\beta_0 + \\sum \\beta_j x_j$ 를 피팅하고, $\\beta_{std,j} = \\beta_j \\frac{\\sigma_{x_j}}{\\sigma_y}$ 와 p-value($<0.05$ 통계적 유의성)를 함께 산출해.",
        "해석이 매우 직관적이지만, Bossung 곡률이나 박막 간섭 같은 강한 비선형성은 선형 모델만으로 설명력이 떨어져(낮은 $R^2$).",
        "4페이지(상관분석 & 다중회귀 탭)",
    ),
    GlossaryTerm(
        "DOE",
        "2⁴ Full Factorial DOE (요인실험계획법 — 주효과 & 교호작용)",
        "데이터·DOE·통계",
        "4개 핵심 변수(Dose, Focus, BARC, PEB)의 저/고(−/+) 2수준 조합 16개를 체계적으로 실험해 단일 효과와 2인자 교호작용을 분해.",
        "변수를 하나씩만 바꿔보면 '두 변수가 합쳐졌을 때 시너지/역효과(교호작용)'를 못 찾아. DOE는 16번의 최소 실험으로 모든 조합 효과를 깔끔하게 분리해 내는 공정 엔지니어 필수 기법이야.",
        "주효과(Main Effect)는 한 변수가 Low→High로 갈 때 평균 CD 변화량이고, 교호작용(Interaction, 예: `Dose × AbsFocus`)은 한 변수의 효과가 다른 변수 수준에 따라 얼마나 달라지는지(Bossung 곡률 변화)를 정량화해.",
        "실제 Fab에서 웨이퍼 실험 비용을 최소화하면서 최적 조건과 핵심 교호작용을 찾을 때 가장 먼저 쓰는 방법이야.",
        "4페이지(2⁴ 요인실험 DOE 파레토 차트)",
    ),
    # --- 6. 머신러닝 & 최적화 ---
    GlossaryTerm(
        "ml_models",
        "Linear / Random Forest / XGBoost & R² · RMSE · CV",
        "머신러닝·최적화",
        "공정 변수로부터 CD를 예측하는 3종 회귀 알고리즘 비교. R²는 설명력(1에 가까울수록 좋음), RMSE는 평균 예측 오차(nm), CV는 교차검증 오차.",
        "Linear는 직선 자로 긋기, Random Forest는 여러 결정나무의 다수결 평균, XGBoost는 앞 나무가 틀린 오차를 뒷 나무가 집중 보완하는 '오답노트 앙상블'이야.",
        "5-Fold **Cross-Validation(CV)**으로 과적합을 점검해. 또한 본 시뮬레이터는 원시 레시피만 넣으면 박막 간섭 진동 때문에 트리 모델 오차가 커지는 점을 해결하기 위해, 인라인 광학 계측(`reflectance`, `eta_abs`)과 간섭 위상 항($\\cos/\\sin(4\\pi n d/\\lambda)$)을 결합한 **Physics-Informed 하이브리드 피처**를 써.",
        "XGBoost는 비선형 상호작용을 매우 잘 잡지만, 학습 데이터에 없던 완전히 새로운 파장/영역에서는 예측이 무너져.",
        "5페이지(모델 성능 비교 탭)",
    ),
    GlossaryTerm(
        "SHAP",
        "SHAP (SHapley Additive exPlanations)",
        "머신러닝·최적화",
        "게임이론(Shapley Value)을 이용해 블랙박스 ML 모델이 특정 CD를 예측한 이유를 각 공정 변수의 기여도(nm)로 정확히 분해하는 XAI 기법.",
        "팀 프로젝트 점수가 90점 나왔을 때 '철수가 +5점, 영희가 -2점 기여했다'처럼, CD 변동에 각 공정 변수가 평균 몇 nm씩 책임이 있는지 공정하게 계산해 주는 도구야.",
        "단순 트리 분기 횟수 기반 중요도와 달리, 각 샘플별 예측 편차를 변수별 기여도 합($\\hat{y} = E[y] + \\sum \\phi_j$)으로 일치성 있게 분해해. 평균 $|\\text{SHAP}|$ 이 큰 변수가 CD 산포의 최우선 관리 대상(Root Cause)이야.",
        "공정 이상 발생 시 엔지니어가 '왜 CD가 틀어졌는가'를 데이터 기반으로 빠르게 진단할 수 있게 해줘.",
        "5페이지(SHAP 원인 분석 차트)",
    ),
    GlossaryTerm(
        "optimizer",
        "Surrogate Model & Process Window 역최적화",
        "머신러닝·최적화",
        "느린 다차원 물리 탐색 대신 빠른 ML 대리모델(Surrogate)로 후보 1,200개를 걸러낸 뒤, 상위 후보를 물리 FEM 엔진으로 최종 검증해 최적 레시피를 찾는 방식.",
        "수천 개 레시피를 전부 정밀 시뮬레이션하면 오래 걸리니까, 빠른 AI로 유망한 8개만 추린 뒤 진짜 물리 엔진으로 '결승전 검증'을 돌리는 2단계 전략이야.",
        "단순히 목표 CD에 맞추는 게 아니라, `Score = PW_Area - 15 × Defect_Risk - 800 × R_sub` 복합 목적함수로 **넓은 Process Window + 낮은 반사율 + 최소 결함 위험**을 동시에 만족하는 강건한(Robust) 레시피를 선정해.",
        "ML의 속도 장점과 물리 모델의 신뢰성을 결합해 실무 적용 가능성을 높인 구조야.",
        "5페이지(최적 공정조건 탐색 탭)",
    ),
    GlossaryTerm(
        "extrapolation",
        "Extrapolation (외삽) 한계 & 물리 인과관계",
        "머신러닝·최적화",
        "학습 범위 안(내삽, Interpolation)에서는 ML이 정확하지만, 학습에 없던 새 물리 영역(외삽, 예: 193nm 학습 → 248nm 평가)에서는 ML이 크게 실패하는 현상.",
        "중학교 수학 문제집만 외운 AI에게 처음 보는 고등학교 물리 문제를 내면 엉뚱한 답을 찍지만, 기본 물리 법칙을 아는 엔지니어는 새 문제도 풀어내는 것과 같아.",
        "특히 Random Forest·XGBoost 같은 트리 기반 모델은 학습 데이터의 최댓값/최솟값 바깥으로 값을 뻗어 나갈 수 없어. 본 시뮬레이터 5페이지에서 193nm(목표 CD 45~80nm)로만 학습한 XGBoost가 248nm(목표 CD 140nm)에서 수십 nm 오차를 내며 붕괴하는 반면, 물리 모델은 계측 노이즈 수준(~0.5nm)을 유지하는 걸 직접 확인할 수 있어.",
        "따라서 **머신러닝은 물리적 인과관계를 증명하거나 대체하는 도구가 아니라**, 물리 모델 위에서 고속 근사·산포 진단·최적화를 돕는 보조 엔진으로 써야 해.",
        "5페이지(ML의 물리적 한계 탭)",
    ),
    # --- 7. 실전 Fab · 전/후 공정 연계 & Run-to-Run ---
    GlossaryTerm(
        "thin_film",
        "Thin Film (박막 증착 공정) & 하부막 영향",
        "실전 Fab·연계 공정",
        "포토 공정 전 웨이퍼 위에 산화막(SiO₂), 폴리실리콘, 금속(Al/Cu) 등을 얇게 쌓는 전 공정. 하부막 두께와 (n, k)가 포토 반사율을 결정함.",
        "그림을 그리기 전에 도화지(산화막/금속판)를 먼저 까는 단계야. 도화지 재질과 두께가 달라지면 빛 반사량도 달라져.",
        "하부 박막 두께 $d_{UL}$ 이 조금만 변해도 다층 박막 간섭 위상이 바뀌어 $R_{sub}$와 $\\eta_{abs}$가 변해. 특히 Al 같은 금속 하부막은 반사율이 매우 높아 BARC 설계가 필수야.",
        "앞단 Thin Film 증착 두께 산포가 크면 포토 노광량 여유(EL%)를 잡아먹으므로, 하부막에 맞는 BARC로 광학 민감도를 낮춰야 해.",
        "7페이지(Step 1 전 공정 설정)",
    ),
    GlossaryTerm(
        "cmp",
        "CMP (화학기계적 연마) & 디싱(Dishing) Defocus",
        "실전 Fab·연계 공정",
        "포토 직전 웨이퍼 표면의 울퉁불퉁한 단차를 평평하게 갈아내는 전 공정. 평탄화가 덜 되면 노광 시 초점 이탈(Defocus)을 유발함.",
        "도장을 찍기 전에 책상 위를 대패로 평평하게 미는 작업이야. 바닥이 움푹 패여(Dishing) 있으면 도장이 흐릿하게 찍혀(Defocus).",
        "High-NA(예: ArFi 1.35)로 갈수록 DOF가 100nm 안팎으로 매우 좁아져서, 앞단 CMP에서 생긴 수십 nm 단차(Dishing/Erosion)가 그대로 노광 Focus 오차와 웨이퍼 산포($\\sigma_{focus}$)로 직결돼.",
        "CMP 균일도를 개선하거나, 앞단 계측값을 받아 스캐너 Focus Offset으로 Feed-Forward 보정(APC)해야 수율을 지킬 수 있어.",
        "7페이지(Step 1 전 공정 CMP 설정)",
    ),
    GlossaryTerm(
        "etch_aci",
        "ADI vs ACI & Etch Bias (식각 바이어스)",
        "실전 Fab·연계 공정",
        "ADI는 포토 현상 직후 CD, ACI는 식각(Etch) 및 세정 후 최종 회로 CD. 식각 중 선폭이 변하는 양(Etch Bias)을 감안해 포토 목표를 잡아야 함.",
        "ADI는 연필 밑그림 두께, ACI는 칼로 파낸 최종 도장 두께야. 칼질할 때 옆이 2nm 더 깎인다면(Etch Bias = -2nm), 밑그림은 미리 2nm 두껍게 그려야 해.",
        "$CD_{ACI} = CD_{ADI} + \\text{Etch Bias}$. 따라서 목표 회로 선폭을 맞추기 위한 포토 목표 선폭은 $CD_{ADI,target} = CD_{ACI,target} - \\text{Etch Bias}$ 야. 또한 식각을 버틸 만큼의 최소 PR 두께($d_{PR} \\ge d_{min,etch}$)도 유지해야 해.",
        "PR을 너무 두껍게 잡으면 Etch는 잘 버티지만 종횡비(AR)가 커져 포토에서 쓰러지고(Collapse), 너무 얇으면 Etch 중 패턴이 다 날아가 버려.",
        "7페이지(Step 4 후공정 Etch 연계)",
    ),
    GlossaryTerm(
        "r2r_apc",
        "Run-to-Run (R2R) / APC 반복 수율 개선",
        "실전 Fab·연계 공정",
        "1차 계측 결과와 데이터 분석을 바탕으로 다음 차수(2차·3차) 레시피(BARC, Dose, Focus, PEB)를 보정해 수율을 끌어올리는 폐루프 공정 제어.",
        "영점 사격 1발 쏘고 표적지 탄착점을 보고(데이터 분석) 조준경을 몇 클릭 돌려서(조치사항) 다음 발을 정중앙에 꽂는 과정이야.",
        "계측된 평균 CD 오차는 Dose/Focus APC 피드백으로 중심을 맞추고, 웨이퍼 공간 산포($3\\sigma$)는 BARC(Swing 억제)·스핀 코팅·PEB 핫플레이트 균일도 개선으로 줄여 수율을 98%+로 수렴시켜.",
        "한 번에 모든 원인을 고치기보다 1) 치명적 광학·결함 제거 → 2) 정밀 타겟/산포 튜닝 순서로 원인을 분해해 검증하는 것이 실무 표준이야.",
        "7페이지(실전 Fab 사이클 & 보고서)",
    ),
]

GLOSSARY_MAP: Dict[str, GlossaryTerm] = {item.key: item for item in GLOSSARY_LIST}

CATEGORIES: List[str] = [
    "전체",
    "광학·해상도",
    "박막간섭·BARC",
    "노광·FEM·결함",
    "코팅·베이크·현상",
    "데이터·DOE·통계",
    "머신러닝·최적화",
    "실전 Fab·연계 공정",
]


def tip(key: str) -> str:
    """Return concise hover tooltip text for a glossary term key."""
    entry = GLOSSARY_MAP.get(key)
    return entry.short_tip if entry is not None else ""


def render_term_card(entry: GlossaryTerm) -> None:
    """Render one glossary term cleanly with undergraduate-level structure."""
    with st.container(border=True):
        st.markdown(f"#### {entry.term}  `{entry.category}`")
        st.markdown(f"**쉬운 직관:** {entry.intuition}")
        st.markdown(f"**물리·공학적 원리:** {entry.physics}")
        st.markdown(f"**변화 시 트레이드오프:** {entry.tradeoff}")
        st.caption(f"시뮬레이터 위치: {entry.where_in_app}")


@st.dialog("포토공정 용어 사전 (학부생 눈높이)", width="large", position="right")
def open_glossary_drawer(default_keys: Sequence[str] = ()) -> None:
    """Right-hand slide-out searchable glossary drawer usable from any page."""
    st.caption("궁금한 영어 약어나 물리 개념을 입력하면 직관 + 수식 원리 + 공정 트레이드오프까지 바로 보여줍니다.")
    query = st.text_input(
        "용어 검색",
        placeholder="예: NA, BARC, Bossung, SWR, η_abs, SHAP, 외삽...",
        key="drawer_glossary_search",
    )
    cat = st.selectbox("카테고리 필터", CATEGORIES, index=0, key="drawer_glossary_cat")

    q = query.strip().lower()
    if not q and cat == "전체" and default_keys:
        st.markdown("**이 페이지에서 자주 나오는 핵심 용어**")
        items = [GLOSSARY_MAP[k] for k in default_keys if k in GLOSSARY_MAP]
    else:
        items = [
            g
            for g in GLOSSARY_LIST
            if (cat == "전체" or g.category == cat)
            and (
                not q
                or q in g.term.lower()
                or q in g.key.lower()
                or q in g.short_tip.lower()
                or q in g.intuition.lower()
                or q in g.physics.lower()
            )
        ]

    if not items:
        st.warning("검색 결과가 없습니다. 다른 키워드(예: CD, NA, BARC, FEM, SHAP)로 검색해 보세요.")
        return

    st.caption(f"표시된 용어: {len(items)}개")
    for entry in items:
        render_term_card(entry)


def render_glossary_toolbar(page_id: str, page_term_keys: Sequence[str]) -> None:
    """Render a compact sidebar quick-help button + inline per-page concept explainer."""
    with st.sidebar:
        st.divider()
        st.markdown("**용어가 헷갈릴 때**")
        if st.button(
            "용어 사전 바로 열기",
            icon=":material/menu_book:",
            key=f"open_glossary_{page_id}",
            width="stretch",
            help="현재 화면을 유지한 채 오른쪽에서 검색 가능한 포토공정 용어 사전을 엽니다.",
        ):
            open_glossary_drawer(page_term_keys)


def render_analogy_cards(cards: Sequence[tuple[str, str, str]]) -> None:
    """Render concise beginner-friendly everyday analogy cards in a clean grid."""
    cols = st.columns(min(len(cards), 3))
    for idx, (title, analogy, physics_link) in enumerate(cards):
        with cols[idx % len(cols)]:
            with st.container(border=True, height="stretch"):
                st.markdown(f"**{title}**")
                st.markdown(analogy)
                st.caption(physics_link)


def render_page_concept_guide(
    page_id: str,
    title: str,
    term_keys: Iterable[str],
    quick_summary: str,
) -> None:
    """Render an on-page collapsible beginner/undergrad physics & term guide."""
    keys = [k for k in term_keys if k in GLOSSARY_MAP]
    with st.expander(title, icon=":material/school:", expanded=False):
        st.markdown(quick_summary)
        selected_label = st.selectbox(
            "이 페이지 용어 골라서 자세히 보기",
            [GLOSSARY_MAP[k].term for k in keys],
            key=f"guide_select_{page_id}",
        )
        selected_entry = next(GLOSSARY_MAP[k] for k in keys if GLOSSARY_MAP[k].term == selected_label)
        render_term_card(selected_entry)
