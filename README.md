# AI 기반 반도체 포토공정 변수 분석 및 최적화 시뮬레이터

- **Live Web App (Streamlit Cloud)**: [https://photo-litho-simulator-2va5ivpwzvtvt4gsxxnar6.streamlit.app/](https://photo-litho-simulator-2va5ivpwzvtvt4gsxxnar6.streamlit.app/)
- **GitHub Repository**: [https://github.com/junyuk-semi/photo-litho-simulator](https://github.com/junyuk-semi/photo-litho-simulator)

> **Synthetic Data Notice**: 본 시뮬레이터의 모든 데이터는 실제 제조사 내부 공정 레시피가 아닌, **표준 광학·포토리소그래피 물리 모델(Rayleigh, 2×2 TMM/S-Matrix, Bossung FEM, Meyerhofer, Arrhenius PEB, Mack 현상 모델)과 현실적 공정 산포 가정에 기반한 가상(합성) 데이터**입니다.

## 프로젝트 목적
- 포토리소그래피(Photo Lithography)의 핵심 물리 원리(Rayleigh 해상도, 다층 박막 간섭 TMM, Standing Wave, BARC, Focus–Exposure Matrix)를 수식·코드로 직접 구현
- **광학(TMM) ↔ FEM(Bossung) 물리 결합**($E_{eff} = E \cdot \eta_{abs}$)을 통해 PR/BARC/하부막 변화가 CD와 Process Window에 미치는 인과관계를 정량 분석
- 물리 기반 가상 Fab 데이터에 데이터 분석(DOE·회귀)과 하이브리드 머신러닝(CD 예측·SHAP 산포 원인 분석·Process Window 역최적화·외삽 한계 증명)을 결합해 공정기술 엔지니어 관점의 의사결정 도구를 구축

## 핵심 문서
- 1단계 물리 설계 명세서: [docs/01_physics_spec.md](docs/01_physics_spec.md)
- 실제 공정 vs 시뮬레이션 한계: [docs/02_limitations.md](docs/02_limitations.md)

## 7단계 구현 완료 기능
- [x] **1단계**: 포토공정 31개 변수 사전, 물리 인과관계(DAG), 지배방정식 명세 및 상수 프리셋 구축
- [x] **2단계**: Rayleigh 해상도($CD = k_1\lambda/NA$) · High-NA/Immersion DOF · OAI 조명계 계산기 (+ EUV 비교)
- [x] **3단계**: 2×2 S-Matrix(TMM) 다층 박막 광학 시뮬레이션 (반사율, 투과율, PR 내부 Standing Wave $I(z)$, Swing Curve, BARC 최적화)
- [x] **4단계**: Optics-Coupled Focus–Exposure Matrix(FEM), Bossung Plot, 최대 내접 Process Window(DOF @ EL%) 및 4대 결함 위험도 진단
- [x] **5단계**: Tier 2 공정 모델(코팅/베이크/현상), 300mm 웨이퍼 2D CDU 맵($3\sigma$), LHS 가상 Fab 데이터 생성, 상관·OLS·$2^4$ DOE 분석
- [x] **6단계**: Physics-Informed 하이브리드 ML(Linear/RF/XGBoost), SHAP 원인 분석, 물리 검증 역최적화 및 **193nm→248nm 외삽 한계 증명**
- [x] **7단계**: Streamlit 멀티페이지 통합 시뮬레이터 + 학부생 눈높이 44개 용어 사전(우측 슬라이드 검색 드로어 & 전 페이지 `?` 툴팁)

## 프로젝트 구조
```text
photo-litho-simulator/
├── README.md
├── requirements.txt
├── .streamlit/config.toml
├── docs/
│   ├── 01_physics_spec.md
│   └── 02_limitations.md
├── src/
│   ├── physics/                # constants, resolution, optics_tmm, exposure_fem, process_models
│   ├── data/                   # LHS synthetic Fab generator, correlation/OLS/2^4 DOE
│   ├── ml/                     # LR/RF/XGBoost + SHAP + extrapolation proof + PW optimizer
│   └── visualization/          # Matplotlib builders
├── app/
│   ├── Home.py                 # Streamlit Cloud Entrypoint
│   ├── glossary.py             # 44-term interactive glossary drawer & tooltips
│   └── pages/                  # Pages 1~6
├── scripts/
│   └── stage2_resolution_report.py
└── tests/                      # 31 automated unit & Streamlit AppTest checks
```

## 로컬 실행 방법
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate  |  macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# Streamlit 통합 웹 시뮬레이터 실행
streamlit run app/Home.py

# 전체 단위/통합 테스트 실행
pytest tests -v
```
