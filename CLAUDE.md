# 약;알다 (MediKnow) 백엔드 컨텍스트

## 프로젝트 개요
한국 의약품 정보 조회 앱 "약;알다"의 FastAPI 백엔드.
약 이름 검색 · OCR 분석 · 병용금기 확인 기능 제공.

## 기획 문서 위치
모든 기획 문서는 `/Users/molt/Desktop/molt_repository/MediKnow/` 에 있음.
코드 작성 전 반드시 참고:
- `backend_spec.csv` — 기능명세서 (비즈니스 로직 · 요청/응답 상세)
- `schema.sql` — Supabase DB 스키마
- `external_api_spec.csv` — 식약처 공공 API 명세 (파라미터 · 응답 필드)
- `api_usage_examples.py` — 외부 API 호출 예시 코드
- `error_codes.csv` — 에러 코드 정의

## 기술 스택
- **FastAPI** + Python 3.11
- **EasyOCR** — 약봉투 텍스트 추출 (한국어 지원)
- **RapidFuzz** — OCR 결과 정규화 · 검색 관련도 정렬 (token_sort_ratio)
- **Claude claude-haiku-4-5** (Anthropic SDK) — 의약 용어 → 쉬운 말 변환
- **Redis** — API 응답 캐싱 (TTL: 약 상세 7일 · 검색 1일 · 병용금기 7일)
- **Supabase** — PostgreSQL DB + Auth
- **httpx** — 외부 API 비동기 호출

## 내부 API 구조 (6개)

| ID | 엔드포인트 | 설명 |
|----|-----------|------|
| OCR-01 | POST /api/v1/ocr/analyze | 이미지 → EasyOCR → RapidFuzz 정규화 → 약 정보 |
| DRUG-01 | GET /api/v1/drugs/search | 약 이름 검색 · RapidFuzz 관련도 정렬 |
| DRUG-02 | GET /api/v1/drugs/{drug_id} | 약 상세 조회 · AI 변환 포함 |
| DRUG-03 | INTERNAL | RapidFuzz 정규화 함수 (엔드포인트 없음) |
| INTERACTION-01 | POST /api/v1/drugs/interaction | 병용금기 확인 |
| AI-01 | INTERNAL | Claude 텍스트 변환 함수 (엔드포인트 없음) |

## 외부 API (식약처 공공 API — 3종 모두 무료)
- **EXT-01** e약은요: `http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList`
- **EXT-02** 낱알식별: `http://apis.data.go.kr/1471000/MdcinGrnIdntfcInfoService03/getMdcinGrnIdntfcInfoList03`
- **EXT-03** DUR: `http://apis.data.go.kr/1471000/DURPrdlstInfoService03/{endpoint}`
  - 병용금기: `/getUsjntTabooInfoList03`
  - 임부금기: `/getPwnmTabooInfoList03`
  - 연령금기: `/getSpcifyAgrdeTabooInfoList03`
- 인증: `serviceKey` 쿼리 파라미터 (Decoded 값 사용 · httpx params= 에 넣으면 자동 인코딩)
- 응답: 기본 XML → `type=json` 파라미터 필수

## DB 스키마 (Supabase PostgreSQL)
```
drugs         — 약 상세 정보 (식약처 원문 + AI 변환 결과)
drug_names    — RapidFuzz 정규화용 전체 품목 목록 (초기 1회 적재 필요)
interactions  — 병용금기 결과 캐시
```

## Redis 캐시 키 규칙
```
drug:{drug_id}              TTL 7일  — 약 상세
search:{정규화된검색어}       TTL 1일  — 검색 결과 목록
interaction:{id1}:{id2}     TTL 7일  — 병용금기 (id1 < id2 오름차순)
```

## 핵심 비즈니스 로직 요약

### AI 변환 (AI-01)
- Claude claude-haiku-4-5 사용 (비용 최소화)
- 식약처 원문 → 중학생도 이해할 수 있는 설명으로 변환
- Pydantic으로 JSON 응답 파싱 · 실패 시 1회 재시도
- 재시도 실패 시 official_raw 원문으로 fallback (서비스 중단 없음)
- Supabase DB에 *_simple 컬럼이 NULL일 때만 호출 (중복 호출 방지)

### RapidFuzz 정규화 (DRUG-03)
- token_sort_ratio 유사도 80% 이상만 허용
- drug_names 테이블 전체와 비교 → 상위 1개 반환

### 검색 관련도 정렬 (DRUG-01)
- 식약처 API 결과 전체에 RapidFuzz token_sort_ratio 계산
- 유사도 내림차순 정렬 후 page/limit 페이지네이션

### 병용금기 교차 비교 (INTERACTION-01)
- 약 A의 병용금기 목록 조회 → MIXTURE_ITEM_SEQ 추출
- 약 B · C의 drug_id와 교차 비교 → 일치하면 forbidden
- drug_ids 오름차순 정렬 후 조합키 생성 (중복 방지)

## 타임아웃 정책
- OCR 처리: 10초
- 식약처 API: 5초
- Claude API: 15초
- 전체 요청: 20초 (DRUG-02 · INTERACTION-01)

## 이미지 전처리 (OCR-01)
EasyOCR 정확도 향상을 위해 순서대로 처리:
1. 그레이스케일 변환
2. 리사이즈 (최대 1280px)
3. 이진화 (threshold)

## 에러 처리 원칙
- AI 실패 → fallback (서비스 중단 없음)
- 식약처 API 실패 → 502 UPSTREAM_ERROR
- 타임아웃 → 504 TIMEOUT
- 전체 에러 목록: `error_codes.csv` 참고

## 개발 시작 순서 (추천)
1. **DRUG-02** — Redis 캐싱 + 식약처 API + AI-01 패턴 한 번에 익히기
2. **DRUG-01** — 검색 + RapidFuzz 정렬
3. **OCR-01** — EasyOCR + 이미지 전처리
4. **INTERACTION-01** — DUR API + 교차 비교 로직

## 로컬 실행
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# .env 파일에 키 입력 후
uvicorn app.main:app --reload
# http://localhost:8000/docs 에서 테스트
```
