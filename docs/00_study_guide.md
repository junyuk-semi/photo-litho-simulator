# 📚 개념 학습 가이드: AI 기반 포토공정 시뮬레이터

- **프로젝트**: [[03.Project/photo-litho-simulator/README|photo-litho-simulator]] · [Live Web App](https://photo-litho-simulator-2va5ivpwzvtvt4gsxxnar6.streamlit.app/)
- **연관 대시보드**: [[01.Dashboard/포트폴리오|🚀 포트폴리오]] · [[01.Dashboard/취업|🏢 취업]]

> [!info] 이 문서는 무엇인가요?
> 이 프로젝트를 처음 보거나 면접 전에 복습할 때, **"코드가 무슨 물리 현상을 풀고 있는지"**를 **① 중·고등학생 비유 → ② 학부 공학 수식 → ③ 실제 코드 모듈** 순서로 한 번에 이해할 수 있게 만든 학습 가이드야.

---

## 1. 이 프로젝트가 해결하려는 문제 한 줄 요약
> **"빛으로 반도체 회로를 찍을 때(포토공정), 빛 파장·렌즈·코팅 두께·초점이 조금만 어긋나도 선폭(CD)이 망가지는데, 이걸 물리 방정식으로 계산하고 AI로 원인까지 찾아내자!"**

---

## 2. 단계별 물리·공학 개념 해설

### ① 해상도와 초점심도 (`src/physics/resolution.py` · 앱 1페이지)
- **중·고등학생 비유**: 도화지에 **붓(빛 파장 $\lambda$)**으로 글씨를 쓸 때 붓이 가늘수록(파장이 짧을수록) 작은 글씨를 쓸 수 있고, **카메라 조리개(렌즈 개구수 $NA$)**를 활짝 열수록 디테일은 선명해지지만 조금만 초점이 어긋나도 사진이 흐려져(아웃포커싱).
- **학부 공학 수식**:
  $$CD_{min} = k_1 \frac{\lambda}{NA}, \qquad DOF = k_2 \frac{\lambda}{NA^2}$$
  - $NA = n \sin\theta$: 액침 노광(Immersion, 물 $n=1.44$)을 쓰면 공기($n=1$)보다 $NA$를 1.35까지 키울 수 있음.
  - **핵심 트레이드오프**: $NA$를 키우면 $CD$는 $1/NA$로 작아지지만, 초점 여유도($DOF$)는 $1/NA^2$로 제곱 속도로 좁아짐!
  - **OAI(사입사 조명)**: 빛을 수직이 아닌 비스듬한 각도로 쏘아 회절광(0차, ±1차)을 렌즈 안에 더 잘 집어넣어 해상도를 높이는 기법.

### ② 다층 박막 간섭과 BARC (`src/physics/optics_tmm.py` · 앱 2페이지)
- **중·고등학생 비유**: 유리창이나 비눗방울에 빛이 반사돼 무지개무늬가 생기는 것처럼, 웨이퍼 위 코팅층(감광액 PR + 하부막) 사이에서 빛이 앞뒤로 튕기며 **물결(정상파, Standing Wave)**을 만들어. 바닥 거울(알루미늄 등)이 빛을 너무 반사하면 패턴 옆면이 울퉁불퉁해지는데, 바닥에 **검은색 무반사 매트(BARC)**를 깔면 깔끔해져.
- **학부 공학 원리**:
  - **2×2 TMM (Transfer Matrix Method)**: 공기 / PR / BARC / 하부막 / 실리콘 각 경계면에서의 전자기파 반사·투과를 2×2 행렬 곱으로 엄밀히 계산함.
  - **Standing Wave $I(z)$** & **Swing Curve**: PR 두께가 $\lambda / (4n)$ 주기마다 반사율($R$)과 필요 노광량이 요동침. BARC의 굴절률($n, k$)과 두께를 최적화해 반사율을 1% 미만으로 억제.

### ③ Focus–Exposure Matrix(FEM) & Process Window (`src/physics/exposure_fem.py` · 앱 3페이지)
- **중·고등학생 비유**: 사진을 잘 찍으려면 **초점(Focus)**과 **노출 시간(Exposure Dose)** 둘 다 적당해야 해. 초점과 노출 시간을 바둑판처럼 바꿔가며 찍어보고, 합격 선폭(목표 CD ±10%) 안에 들어오는 **"안전한 직사각형 구역(Process Window)"**을 찾는 거야.
- **학부 공학 원리**:
  - **Optics-Coupled FEM**: 2단계 TMM에서 계산한 유효 흡수 효율 $\eta_{abs}$를 받아 $E_{eff} = E \cdot \eta_{abs}$ 로 노광량과 광학 물리를 직접 결합.
  - **Bossung Plot**: Focus($\Delta z$)에 따른 CD의 U자형/역U자형 곡선. Dose가 적정할 때 곡선이 가장 평평(Iso-focal)함.
  - **4대 결함**: Dose 부족/과다, Defocus로 생기는 **Pattern Collapse**(기둥 쓰러짐), **Scum**(잔여물), **Bridging**(선 붙음), **Notching**(측면 패임).

### ④ 300mm 웨이퍼 균일도(CDU) & 통계/DOE (`src/physics/process_models.py`, `src/data/` · 앱 4페이지)
- **중·고등학생 비유**: 30cm 큰 피자를 오븐에 구울 때 가운데랑 테두리 온도가 다르면 익는 정도가 달라지듯, 300mm 웨이퍼도 스핀 코팅 두께와 베이크(PEB) 온도 차이 때문에 위치마다 선폭(CD)이 조금씩 달라져.
- **학부 공학 원리**:
  - **Tier 2 공정 모델**: 스핀 코팅(Meyerhofer), PEB 열적 산 확산(Arrhenius), 현상 속도(Mack 모델).
  - **CDU ($3\sigma$)**: 웨이퍼 전체 다이(Die) 선폭의 표준편차×3. 작을수록 수율이 높음.
  - **LHS & $2^4$ DOE / OLS**: 가상 Fab 데이터를 체계적으로 생성하고, 어느 변수(Dose, Focus, PEB 온도, PR 두께)가 CD에 가장 크게 작용하는지 회귀분석으로 정량화.

### ⑤ 하이브리드 ML & 외삽 한계 증명 (`src/ml/` · 앱 5페이지)
- **중·고등학생 비유**: 수학 공식을 아는 사람(물리 모델)과 기출문제만 외운 학생(머신러닝)의 차이! 기출문제 범위 안에서는 AI가 엄청 빠르게 맞추지만, **완전히 새로운 시험 범위(193nm 학습 → 248nm 예측)**가 나오면 물리 공식을 모르면 엉뚱한 답을 내놔.
- **공학 포인트**:
  - **SHAP**: 블랙박스 AI(XGBoost/RF)가 왜 CD가 커졌다고 예측했는지 변수별 기여도를 분해해 설명.
  - **외삽(Extrapolation) 한계 증명**: 물리 기반 모델 vs 순수 데이터 ML을 비교해 **"공정기술 엔지니어는 AI를 쓰더라도 반드시 물리 원리를 알아야 한다"**는 걸 코드와 그래프로 증명.

### ⑥ 실전 Fab 사이클 & Run-to-Run 수율 개선 (`src/fab_cycle.py` · 앱 7페이지)
- **중·고등학생 비유**: 활을 한 번 쏘고(1차 공정) 과녁에 맞은 위치(`ADI` 계측)를 본 뒤, 조준경을 왼쪽으로 몇 눈금 돌려서 다시 쏘는(2차·3차 보정) 과정!
- **공학 흐름**: 전 공정(`Thin Film`, `CMP` 단차) → 포토 8단계 → `ADI` 계측 & CAPA 보고서 → `Run-to-Run(R2R)` 레시피 자동 보정 → 후공정 `Etch Bias` & 최종 `ACI` 수율.

---

## 3. 코드 ↔ 개념 빠른 매핑표
| 공부하고 싶은 주제 | 확인할 소스 파일 | 관련 강의자료 |
| :--- | :--- | :--- |
| 빛 파장·NA·DOF | `src/physics/resolution.py` | [[02.Sources/강의자료/집적회로공정/MD/Week7_Fabrication of IC_Photolitho1\|Week7 MD]] |
| 다층 박막 간섭·BARC | `src/physics/optics_tmm.py` | [[02.Sources/강의자료/집적회로공정/MD/Week9_Fabrication of IC_Photolitho 2\|Week9 MD]] |
| Bossung FEM·Process Window | `src/physics/exposure_fem.py` | [[03.Project/photo-litho-simulator/docs/01_physics_spec\|01_physics_spec]] |
| ML·SHAP·외삽 증명 | `src/ml/` | — |
| 실전 Fab 연계 & 한계 | `src/fab_cycle.py` | [[03.Project/photo-litho-simulator/docs/02_limitations\|02_limitations]] |
