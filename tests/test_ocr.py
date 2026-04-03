"""
OCR-01 이미지 분석 테스트.
"""
import io
import pytest
from unittest.mock import AsyncMock, patch
from PIL import Image
from app.models.drug import DrugSearchResponse, DrugSearchItem, DrugDetailResponse, OfficialRaw


def make_image_bytes() -> bytes:
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


FAKE_SEARCH_RESULT = DrugSearchResponse(
    query="타이레놀", total=1, page=1, total_pages=1,
    results=[DrugSearchItem(drug_id="202005623", name="어린이타이레놀산", relevance_score=0.9)],
)

FAKE_DETAIL = DrugDetailResponse(
    drug_id="202005623",
    name="어린이타이레놀산160밀리그램(아세트아미노펜)",
    manufacturer="한국존슨앤드존슨판매(유)",
    summary="열과 통증을 내려주는 약입니다.",
    effect_simple="해열 효과가 있습니다.",
    caution_simple="술 마신 후 먹지 마세요.",
    side_effect_simple="메스꺼움이 생길 수 있어요.",
    dosage_simple="1회 1정 드세요.",
    official_raw=OfficialRaw(effect="해열", caution="주의", side_effect="구역"),
)


@pytest.mark.asyncio
async def test_ocr_invalid_file_type(client):
    """지원하지 않는 파일 형식 → 400."""
    resp = await client.post(
        "/api/v1/ocr/analyze",
        files={"image": ("test.pdf", b"fake pdf content", "application/pdf")},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_FILE_TYPE"


@pytest.mark.asyncio
async def test_ocr_image_too_large(client):
    """10MB 초과 이미지 → 413."""
    large_bytes = b"0" * (10 * 1024 * 1024 + 1)
    resp = await client.post(
        "/api/v1/ocr/analyze",
        files={"image": ("test.png", large_bytes, "image/png")},
    )
    assert resp.status_code == 413
    assert resp.json()["detail"]["code"] == "IMAGE_TOO_LARGE"


@pytest.mark.asyncio
async def test_ocr_no_text_extracted(client):
    """OCR 텍스트 추출 결과 없음 → 422."""
    with patch("app.routers.ocr.extract_drug_names", new=AsyncMock(return_value=([], []))):
        resp = await client.post(
            "/api/v1/ocr/analyze",
            files={"image": ("test.png", make_image_bytes(), "image/png")},
        )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "OCR_FAILED"


@pytest.mark.asyncio
async def test_ocr_success(client):
    """OCR 성공 → 약 정보 반환."""
    with patch("app.routers.ocr.extract_drug_names", new=AsyncMock(return_value=(["타이레놀"], ["타이레놀"]))), \
         patch("app.routers.ocr.search_drugs", new=AsyncMock(return_value=FAKE_SEARCH_RESULT)), \
         patch("app.routers.ocr.get_drug_detail", new=AsyncMock(return_value=FAKE_DETAIL)):

        resp = await client.post(
            "/api/v1/ocr/analyze",
            files={"image": ("test.png", make_image_bytes(), "image/png")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["ocr_raw"] == ["타이레놀"]
    assert len(data["drugs"]) == 1
    assert data["drugs"][0]["drug_id"] == "202005623"
