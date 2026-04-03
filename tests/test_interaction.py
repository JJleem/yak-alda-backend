"""
INTERACTION-01 병용금기 확인 테스트.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


FAKE_DRUG_ROWS = {
    "202005623": {"drug_id": "202005623", "name": "어린이타이레놀산160밀리그램"},
    "200200734": {"drug_id": "200200734", "name": "영진아스피린장용정"},
}

FAKE_DUR_FORBIDDEN = {
    "body": {
        "items": [
            {
                "MIXTURE_ITEM_SEQ": "202005623",  # 타이레놀이 아스피린의 병용금기 대상
                "MIXTURE_ITEM_NAME": "어린이타이레놀산160밀리그램",
                "PROHBT_CONTENT": "병용 시 혈액독성 위험",
            }
        ]
    }
}

FAKE_DUR_SAFE = {"body": {"items": []}}


@pytest.mark.asyncio
async def test_interaction_insufficient_drugs(client):
    """drug_ids 1개 → 400."""
    resp = await client.post(
        "/api/v1/drugs/interaction",
        json={"drug_ids": ["202005623"]},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INSUFFICIENT_DRUGS"


@pytest.mark.asyncio
async def test_interaction_invalid_drug_id(client):
    """존재하지 않는 drug_id → 400."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    mock_db = AsyncMock()
    mock_db.fetchrow = AsyncMock(return_value=None)  # DB에 없음

    with patch("app.services.interaction_service.get_redis", return_value=mock_redis), \
         patch("app.services.interaction_service.get_db", return_value=mock_db):
        resp = await client.post(
            "/api/v1/drugs/interaction",
            json={"drug_ids": ["999999999", "888888888"]},
        )

    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_DRUG_ID"


@pytest.mark.asyncio
async def test_interaction_safe(client):
    """병용금기 없음 → safe 반환."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    mock_db = AsyncMock()
    mock_db.fetchrow = AsyncMock(side_effect=lambda q, drug_id: FAKE_DRUG_ROWS.get(drug_id))
    mock_db.execute = AsyncMock()

    with patch("app.services.interaction_service.get_redis", return_value=mock_redis), \
         patch("app.services.interaction_service.get_db", return_value=mock_db), \
         patch("httpx.AsyncClient") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=FAKE_DUR_SAFE)
        mock_httpx.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await client.post(
            "/api/v1/drugs/interaction",
            json={"drug_ids": ["202005623", "200200734"]},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["result"] == "safe"
    assert data["level"] == "safe"


@pytest.mark.asyncio
async def test_interaction_forbidden(client):
    """병용금기 있음 → forbidden 반환."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    mock_db = AsyncMock()
    mock_db.fetchrow = AsyncMock(side_effect=lambda q, drug_id: FAKE_DRUG_ROWS.get(drug_id))
    mock_db.execute = AsyncMock()

    # 첫 번째 약 조회 시 FORBIDDEN 응답, 두 번째는 SAFE
    responses = [FAKE_DUR_FORBIDDEN, FAKE_DUR_SAFE]
    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value=responses[min(call_count, 1)])
        call_count += 1
        return resp

    with patch("app.services.interaction_service.get_redis", return_value=mock_redis), \
         patch("app.services.interaction_service.get_db", return_value=mock_db), \
         patch("httpx.AsyncClient") as mock_httpx, \
         patch("app.services.interaction_service.translate_drug_info", return_value=None):
        mock_httpx.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=mock_get))
        mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await client.post(
            "/api/v1/drugs/interaction",
            json={"drug_ids": ["202005623", "200200734"]},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["result"] == "forbidden"
    assert data["level"] == "danger"


@pytest.mark.asyncio
async def test_interaction_cache_hit(client):
    """Redis 캐시 HIT → 즉시 반환."""
    cached = {
        "drugs": [{"drug_id": "202005623", "name": "타이레놀"}, {"drug_id": "200200734", "name": "아스피린"}],
        "result": "safe",
        "level": "safe",
        "result_simple": None,
        "official_raw": None,
        "disclaimer": "이 정보는 참고용이며 진단·처방을 대체하지 않습니다. 복용 전 전문가와 상담하세요.",
    }

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps(cached))

    mock_db = AsyncMock()
    mock_db.fetchrow = AsyncMock(side_effect=lambda q, drug_id: FAKE_DRUG_ROWS.get(drug_id))

    with patch("app.services.interaction_service.get_redis", return_value=mock_redis), \
         patch("app.services.interaction_service.get_db", return_value=mock_db):
        resp = await client.post(
            "/api/v1/drugs/interaction",
            json={"drug_ids": ["202005623", "200200734"]},
        )

    assert resp.status_code == 200
    assert resp.json()["result"] == "safe"
