# 실제 포토공정 데이터 vs. 물리 기반 시뮬레이션의 한계

- 상위 문서: [[03.Project/photo-litho-simulator/docs/01_physics_spec|01_physics_spec]]
- 프로젝트 홈: [[03.Project/photo-litho-simulator/README|photo-litho-simulator]]

---

## 1. 가상 데이터 사용 원칙
실제 반도체 제조사(삼성전자, TSMC 등)의 공정 레시피·인라인 계측 데이터(CD-SEM, OCD)는 보안상 외부 공개가 불가능하다. 따라서 본 프로젝트는:
1. 검증된 포토리소그래피 물리 방정식(Rayleigh, TMM, Bossung, Meyerhofer, Mack)으로 결정론적 기준값을 계산하고,
2. 실제 팹의 산포 구조(웨이퍼 내 반경 방향 코팅/온도 구배, 샷별 Focus/Dose 편차, 계측 노이즈)를 확률 항으로 중첩해 **가상(합성) Fab 데이터**를 생성한다.
3. 모든 UI 화면 및 리포트에 **가상 시뮬레이션 데이터임**을 명시한다.

---

## 2. 실제 공정과 본 시뮬레이터의 핵심 차이

| 구분 | 본 시뮬레이터 (1D/준-2D 해석·수치 모델) | 실제 반도체 양산 Fab 공정 | 실제 적용 시 영향 |
| :--- | :--- | :--- | :--- |
| **광학 회절 & 편광** | 스칼라/1D TMM 및 근사 Aerial Image | 3D 엄밀 전자기장(RCWA/FDTD), High-NA 벡터 편광 효과, 렌즈 수차(Zernike) | ArFi($NA=1.35$) 고각도 입사에서 편광별 콘트라스트 차이 및 Intra-field 수차 오차 발생 |
| **하부막 단차 (Topography)** | 평탄한 다층 박막(Planar Stack) 가정 | 실제 소자는 3D 단차 존재 (예: [[02.Sources/강의자료/집적회로공정/MD/Week9_Fabrication of IC_Photolitho 2|Week 9 Slide 20]]의 알루미늄 경사면 $\theta = 60^\circ\sim 70^\circ$ 반사) | 경사면 산란광에 의한 국부적 Notching은 1D TMM만으로 정밀 예측 불가 |
| **레지스트 화학 (CAR)** | 유효 산 확산 길이($L_{diff}$) + Mack 근사식 | 3D 산 생성–확산–퀜처(Quencher) 중화–탈보호 결합 PDE + 확률적 분자 노이즈(Stochastics) | 미세 선폭에서 LER/LWR(선폭 거칠기) 및 확률적 브리지/단선 결함 예측 한계 |
| **마스크 & RET** | 이상적 1D Line/Space + 조명계 계수 근사 | OPC(Optical Proximity Correction), SRAF, 위상반전마스크(PSM), 마스크 3D 효과 | 2D 코너 라운딩, 라인 끝단 단축(Line-end shortening)은 2D 마스크 시뮬레이션 필요 |
| **EUV (13.5nm)** | 2단계 해상도/DOF 비교 차트에만 포함 | 반사형 브래그 다층 미러, 6° 경사 입사 Shadowing, 광자 샷 노이즈(Photon Shot Noise) | DUV용 TMM/BARC 모델은 EUV에 직접 적용 불가 |
| **공정 드리프트 & 상호작용** | 독립 정규/반경 산포 노이즈로 근사 | 장비 노후화, 챔버 오염, 웨이퍼 휨(Warpage), 이전/이후 공정(CMP, Etch) 로딩 효과 | 시계열 드리프트 보정(APC/Run-to-Run Control) 및 식각 바이어스(ADI → ACI) 모델링 필요 |

---

## 3. 실제 양산 공정 도입 시 고도화 방향 (엔지니어 관점)
1. **ADI → ACI 연계**: 현재는 현상 후(ADI, After Development Inspection) CD 기준이나, 실제 소자 성능은 식각 후(ACI, After Cleaning Inspection) CD에 좌우되므로 Etch Bias 모델 결합 필요.
2. **실측 데이터 캘리브레이션(Model Calibration)**: 실제 Fab의 FEM 웨이퍼 CD-SEM 계측 데이터를 확보하면, 본 시뮬레이터의 물리 파라미터($S_E, \kappa_0, \kappa_E, E_{iso}, n, k$)를 비선형 최소제곱법으로 피팅해 **물리 기반 하이브리드 디지털 트윈**으로 확장 가능.
3. **Physics-Informed ML (PINN / Hybrid Residual Learning)**: 순수 ML이 외삽 구간에서 무너지는 한계를 보완하기 위해, 물리 모델의 예측값과 실측값의 **잔차(Residual)**만 ML로 학습하는 하이브리드 구조가 현업에 가장 적합함.
