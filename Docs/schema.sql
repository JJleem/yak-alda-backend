-- =====================================================
-- MediKnow (약;알다) DB 스키마
-- PostgreSQL (Neon 서버리스)
-- =====================================================


-- =====================================================
-- 1. drugs 테이블
-- 용도: 식약처 API 응답 + AI 변환 결과 저장
-- 연관 API: OCR-01 / DRUG-01 / DRUG-02 / AI-01
-- =====================================================
CREATE TABLE drugs (
    -- 식별자
    drug_id         TEXT PRIMARY KEY,           -- 식약처 품목기준코드 (itemSeq) · Redis 캐시 키로도 사용

    -- 기본 정보 [식약처 원문]
    name            TEXT        NOT NULL,        -- 약 이름 (itemName)
    manufacturer    TEXT,                        -- 제조사 (entpName)
    image_url       TEXT,                        -- 낱알 이미지 URL (itemImage)

    -- 식약처 원문 (AI 변환 전 원본 보존)
    effect_raw      TEXT,                        -- 효능 원문 (efcyQesitm)
    dosage_raw      TEXT,                        -- 사용법 원문 (useMethodQesitm)
    caution_raw     TEXT,                        -- 주의사항 원문 (atpnQesitm + atpnWarnQesitm 합산)
    side_effect_raw TEXT,                        -- 부작용 원문 (seQesitm)
    interaction_raw TEXT,                        -- 상호작용 원문 (intrcQesitm)
    storage_raw     TEXT,                        -- 보관법 원문 (depositMethodQesitm)

    -- AI 변환 결과 [AI-01 생성] · 첫 조회 시 NULL → AI-01 호출 후 채움
    summary         TEXT,                        -- 한 줄 요약
    effect_simple   TEXT,                        -- 효능 쉬운 말
    dosage_simple   TEXT,                        -- 사용법 쉬운 말
    caution_simple  TEXT,                        -- 주의사항 쉬운 말
    side_effect_simple TEXT,                     -- 부작용 쉬운 말

    -- 타임스탬프
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- updated_at 자동 갱신 트리거
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER drugs_updated_at
    BEFORE UPDATE ON drugs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- 검색 성능용 인덱스
CREATE INDEX idx_drugs_name ON drugs (name);


-- =====================================================
-- 2. drug_names 테이블
-- 용도: RapidFuzz 정규화 전용 경량 조회 테이블 (DRUG-03)
--       식약처 품목 전체 목록 사전 적재 필요 (초기 1회 세팅)
--       drugs 테이블은 실제 조회된 약만 저장 vs
--       drug_names 는 식약처 전체 품목명 목록 (~30,000건)
-- =====================================================
CREATE TABLE drug_names (
    drug_id         TEXT PRIMARY KEY,            -- 식약처 품목기준코드
    official_name   TEXT        NOT NULL,        -- 공식 품목명 (정규화 기준)
    manufacturer    TEXT                         -- 제조사 (동명이약 구분용)
);

-- RapidFuzz 매칭 성능용 인덱스
CREATE INDEX idx_drug_names_official ON drug_names (official_name);


-- =====================================================
-- 3. interactions 테이블
-- 용도: 병용금기 확인 결과 저장
-- 연관 API: INTERACTION-01 / AI-01
-- =====================================================
CREATE TABLE interactions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 비교 약 쌍 (항상 오름차순 정렬 후 저장 → 중복 방지)
    drug_id_1       TEXT        NOT NULL REFERENCES drugs(drug_id),
    drug_id_2       TEXT        NOT NULL REFERENCES drugs(drug_id),

    -- 병용금기 결과
    result          TEXT        NOT NULL CHECK (result IN ('safe', 'caution', 'forbidden', 'unknown')),
    level           TEXT        NOT NULL CHECK (level IN ('safe', 'warning', 'danger')),

    -- DUR 원문 + AI 변환 결과
    official_raw    TEXT,                        -- DUR API 원문 (없으면 NULL)
    result_simple   TEXT,                        -- AI-01 쉬운 말 변환 (없으면 NULL)

    created_at      TIMESTAMPTZ DEFAULT NOW(),

    -- 같은 약 쌍 중복 저장 방지 (A-B 와 B-A 를 동일하게 취급)
    UNIQUE (drug_id_1, drug_id_2)
);

-- 조합 조회 성능용 인덱스
CREATE INDEX idx_interactions_pair ON interactions (drug_id_1, drug_id_2);


-- =====================================================
-- Redis 캐시 키 규칙 (코드 참고용 주석 — DB에 저장 안 함)
-- =====================================================
-- drug:{drug_id}              → 약 상세 정보 (TTL 7일)  · DRUG-02 / OCR-01
-- search:{정규화된검색어}       → 검색 결과 목록 (TTL 1일) · DRUG-01
-- interaction:{id1}:{id2}     → 병용금기 결과 (TTL 7일)  · INTERACTION-01
--                               ※ id1 < id2 오름차순 정렬 후 키 생성


-- =====================================================
-- 초기 데이터 세팅 가이드 (개발 시작 전 1회 실행)
-- =====================================================
-- drug_names 테이블에 식약처 전체 품목 목록 적재 필요
-- 방법: 식약처 e약은요 API를 pageNo 반복 호출하여 전체 수집
--       또는 공공데이터포털 파일 데이터 다운로드 후 bulk insert
--
-- 예시 Python 스크립트 흐름:
--   page = 1
--   while True:
--       items = call_easydruginfo(pageNo=page, numOfRows=100)
--       if not items: break
--       bulk_insert into drug_names(drug_id, official_name, manufacturer)
--       page += 1
