"""
DRUG-01 (검색) / DRUG-02 (상세) 테스트.
외부 API, DB, Redis 는 모두 Mock 처리.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from tests.conftest import FAKE_API_RESPONSE, FAKE_AI_TRANSLATION, make_fake_db_row


# ─────────────────────────────────────────────
# DRUG-02 약 상세 조회
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_drug_detail_cache_hit(client):
    """Redis 캐시 HIT → 즉시 반환."""
    cached_data = {
        "drug_id": "202005623",
        "name": "어린이타이레놀산160밀리그램(아세트아미노펜)",
        "manufacturer": "한국존슨앤드존슨판매(유)",
        "summary": "열과 통증을 내려주는 약입니다.",
        "effect_simple": "해열 효과가 있습니다.",
        "caution_simple": "술 마신 후 먹지 마세요.",
        "side_effect_simple": "메스꺼움이 생길 수 있어요.",
        "dosage_simple": "1회 1정 드세요.",
        "official_raw": {"effect": "해열", "caution": "주의", "side_effect": "구역"},
        "disclaimer": "이 정보는 참고용이며 진단·처방을 대체하지 않습니다. 복용 전 전문가와 상담하세요.",
    }

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

    with patch("app.services.drug_service.get_redis", return_value=mock_redis):
        resp = await client.get("/api/v1/drugs/202005623")

    assert resp.status_code == 200
    data = resp.json()
    assert data["drug_id"] == "202005623"
    assert data["summary"] == "열과 통증을 내려주는 약입니다."


@pytest.mark.asyncio
async def test_drug_detail_db_hit(client):
    """Redis MISS → DB HIT → AI 변환 없이 반환 (AI 컬럼 이미 채워짐)."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    mock_db = AsyncMock()
    mock_db.fetchrow = AsyncMock(return_value=make_fake_db_row(with_ai=True))

    with patch("app.services.drug_service.get_redis", return_value=mock_redis), \
         patch("app.services.drug_service.get_db", return_value=mock_db):
        resp = await client.get("/api/v1/drugs/202005623")

    assert resp.status_code == 200
    data = resp.json()
    assert data["drug_id"] == "202005623"
    assert data["effect_simple"] is not None


@pytest.mark.asyncio
async def test_drug_detail_not_found(client):
    """Redis MISS → DB MISS → API도 없음 → 404."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    mock_db = AsyncMock()
    mock_db.fetchrow = AsyncMock(return_value=None)
    mock_db.execute = AsyncMock()

    empty_response = {"body": {"items": None}}

    with patch("app.services.drug_service.get_redis", return_value=mock_redis), \
         patch("app.services.drug_service.get_db", return_value=mock_db), \
         patch("httpx.AsyncClient") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=empty_response)
        mock_httpx.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await client.get("/api/v1/drugs/999999999")

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "DRUG_NOT_FOUND"


@pytest.mark.asyncio
async def test_drug_detail_upstream_error(client):
    """식약처 API 실패 → 502."""
    import httpx as _httpx

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    mock_db = AsyncMock()
    mock_db.fetchrow = AsyncMock(return_value=None)

    with patch("app.services.drug_service.get_redis", return_value=mock_redis), \
         patch("app.services.drug_service.get_db", return_value=mock_db), \
         patch("httpx.AsyncClient") as mock_httpx:
        mock_httpx.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(get=AsyncMock(side_effect=_httpx.HTTPStatusError("err", request=MagicMock(), response=MagicMock())))
        )
        mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await client.get("/api/v1/drugs/202005623")

    assert resp.status_code == 502
    assert resp.json()["detail"]["code"] == "UPSTREAM_ERROR"


# ─────────────────────────────────────────────
# DRUG-01 약 검색
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_success(client):
    """검색 성공 → 결과 반환 + relevance_score 내림차순."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    with patch("app.services.drug_service.get_redis", return_value=mock_redis), \
         patch("httpx.AsyncClient") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=FAKE_API_RESPONSE)
        mock_httpx.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await client.get("/api/v1/drugs/search?q=타이레놀")

    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "타이레놀"
    assert data["total"] >= 1
    assert "relevance_score" in data["results"][0]


@pytest.mark.asyncio
async def test_search_empty_query(client):
    """빈 검색어 → 422."""
    resp = await client.get("/api/v1/drugs/search?q=")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_no_result(client):
    """검색 결과 없음 → 404."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    empty_response = {"body": {"items": []}}

    with patch("app.services.drug_service.get_redis", return_value=mock_redis), \
         patch("httpx.AsyncClient") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=empty_response)
        mock_httpx.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await client.get("/api/v1/drugs/search?q=존재하지않는약이름xyz")

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "NO_RESULT"
