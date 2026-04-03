"""
테스트 공통 설정.
실제 외부 API / DB / Redis 호출 없이 테스트하기 위한 Mock 설정.
"""
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app

# ── 식약처 API 가짜 응답 ──────────────────────────────────────────────────────
FAKE_DRUG = {
    "itemSeq": "202005623",
    "itemName": "어린이타이레놀산160밀리그램(아세트아미노펜)",
    "entpName": "한국존슨앤드존슨판매(유)",
    "efcyQesitm": "해열 및 진통에 사용합니다.",
    "useMethodQesitm": "1회 1정 복용하세요.",
    "atpnQesitm": "음주 후 복용하지 마세요.",
    "atpnWarnQesitm": None,
    "seQesitm": "구역, 구토가 나타날 수 있습니다.",
    "intrcQesitm": None,
    "depositMethodQesitm": "실온 보관",
    "itemImage": None,
}

FAKE_API_RESPONSE = {
    "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
    "body": {"pageNo": 1, "totalCount": 1, "numOfRows": 10, "items": [FAKE_DRUG]},
}

# ── AI 가짜 응답 ──────────────────────────────────────────────────────────────
FAKE_AI_TRANSLATION = {
    "summary": "열과 통증을 내려주는 약입니다.",
    "effect_simple": "해열 및 진통 효과가 있습니다.",
    "caution_simple": "술 마신 후에는 먹지 마세요.",
    "side_effect_simple": "메스꺼움이 생길 수 있어요.",
    "dosage_simple": "1회 1정 드세요.",
}

# ── DB 가짜 행 ────────────────────────────────────────────────────────────────
def make_fake_db_row(with_ai=True):
    row = dict(FAKE_DRUG)
    row["drug_id"] = "202005623"
    row["name"] = FAKE_DRUG["itemName"]
    row["manufacturer"] = FAKE_DRUG["entpName"]
    row["effect_raw"] = FAKE_DRUG["efcyQesitm"]
    row["dosage_raw"] = FAKE_DRUG["useMethodQesitm"]
    row["caution_raw"] = FAKE_DRUG["atpnQesitm"]
    row["side_effect_raw"] = FAKE_DRUG["seQesitm"]
    row["image_url"] = None
    row["interaction_raw"] = None
    row["storage_raw"] = FAKE_DRUG["depositMethodQesitm"]
    if with_ai:
        row["summary"] = FAKE_AI_TRANSLATION["summary"]
        row["effect_simple"] = FAKE_AI_TRANSLATION["effect_simple"]
        row["caution_simple"] = FAKE_AI_TRANSLATION["caution_simple"]
        row["side_effect_simple"] = FAKE_AI_TRANSLATION["side_effect_simple"]
        row["dosage_simple"] = FAKE_AI_TRANSLATION["dosage_simple"]
    else:
        row["summary"] = None
        row["effect_simple"] = None
        row["caution_simple"] = None
        row["side_effect_simple"] = None
        row["dosage_simple"] = None
    return row


@pytest_asyncio.fixture
async def client():
    """테스트용 HTTP 클라이언트. 실제 서버 없이 앱에 직접 요청."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
