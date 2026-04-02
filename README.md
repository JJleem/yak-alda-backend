# 약;알다 Backend

의약품 정보 조회 · OCR 분석 · 병용금기 확인 서비스 백엔드

**Stack:** FastAPI · Python 3.11 · Redis · Supabase · EasyOCR · Claude API

---

## 프로젝트 구조

```
app/
├── main.py              # FastAPI 앱 진입점 · 라우터 등록
├── routers/             # 엔드포인트
│   ├── drugs.py         # DRUG-01 (검색) · DRUG-02 (상세)
│   ├── ocr.py           # OCR-01 (이미지 분석)
│   └── interaction.py   # INTERACTION-01 (병용금기)
├── services/            # 비즈니스 로직
├── models/              # Pydantic 요청·응답 스키마
└── core/
    ├── config.py        # 환경변수 로드
    └── redis.py         # Redis 연결 관리
```

---

## API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/drugs/search?q={약이름}` | 약 이름 검색 |
| GET | `/api/v1/drugs/{drug_id}` | 약 상세 조회 |
| POST | `/api/v1/ocr/analyze` | 약봉투 이미지 OCR 분석 |
| POST | `/api/v1/drugs/interaction` | 병용금기 확인 |
| GET | `/health` | 서버 상태 확인 |

API 명세 상세: `docs/backend_spec.csv` 참고
로컬 실행 후 http://localhost:8000/docs 에서 Swagger UI 확인 가능

---

## 로컬 개발 환경 세팅

### 1. 레포 클론

```bash
git clone https://github.com/JJleem/yak-alda-backend.git
cd yak-alda-backend
```

### 2. 가상환경 생성 및 패키지 설치

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 환경변수 설정

```bash
cp .env.example .env
# .env 파일 열어서 값 입력
```

| 변수 | 설명 |
|------|------|
| `SERVICE_KEY` | 공공데이터포털 API 인증키 (Decoded 값) |
| `REDIS_URL` | Redis 연결 URL |
| `ANTHROPIC_API_KEY` | Claude API 키 |
| `SUPABASE_URL` | Supabase 프로젝트 URL |
| `SUPABASE_KEY` | Supabase anon key |

### 4. Redis 로컬 실행 (Docker)

```bash
docker run -d -p 6379:6379 redis:7
```

### 5. 서버 실행

```bash
uvicorn app.main:app --reload
```

→ http://localhost:8000/docs 에서 API 테스트

---

## 프론트 개발자와 로컬 연동 (ngrok)

```bash
# 설치: https://ngrok.com
ngrok http 8000
# 발급된 URL을 프론트 개발자에게 공유
```

---

## 브랜치 전략

```
main      배포 브랜치 (직접 커밋 금지)
develop   개발 통합 브랜치
feature/* 기능 개발 브랜치
```

```bash
# 새 기능 개발 시
git checkout develop
git checkout -b feature/drug-search
# 작업 후
git push origin feature/drug-search
# → develop으로 PR
```

---

## 외부 API

| API | 용도 | 인증 |
|-----|------|------|
| 식약처 e약은요 | 약 정보 조회 | SERVICE_KEY |
| 식약처 낱알식별 | 알약 모양·색상 검색 | SERVICE_KEY |
| 식약처 DUR | 병용금기·임부금기 조회 | SERVICE_KEY |

상세 명세: `docs/external_api_spec.csv` 참고
