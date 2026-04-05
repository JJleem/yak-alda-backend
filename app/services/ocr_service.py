import base64
import io
import json
import logging
from typing import Optional

import anthropic
from PIL import Image
from rapidfuzz import fuzz

from app.core.config import ANTHROPIC_API_KEY
from app.core.database import get_db

logger = logging.getLogger(__name__)

_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

VISION_PROMPT = (
    "이 이미지는 한국 약봉투 또는 약 포장지입니다.\n"
    "이미지에서 약 품목명만 추출해주세요.\n\n"
    "[추출 규칙]\n"
    "- 약 품목명만 추출 (제조사명, 용량, 복용법, 날짜, 환자명 제외)\n"
    "- 괄호 안 성분명 포함해서 추출 (예: 타이레놀정500밀리그램(아세트아미노펜))\n"
    "- 한 봉투에 여러 약이 있으면 모두 추출\n"
    "- 약 이름이 보이지 않으면 빈 배열 반환\n\n"
    "[예시]\n"
    "입력: 약봉투에 '타이레놀정500밀리그램', '아모잘탄정5/50밀리그램' 텍스트 보임\n"
    '출력: {"drug_names": ["타이레놀정500밀리그램", "아모잘탄정5/50밀리그램"]}\n\n'
    "반드시 아래 JSON 형식으로만 응답하세요:\n"
    '{"drug_names": ["약이름1", "약이름2"]}'
)


def _resize_image(image_bytes: bytes, max_size: int = 1280) -> bytes:
    """토큰 절약을 위해 이미지 리사이즈 (최대 1280px)."""
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    fmt = img.format or "JPEG"
    img.save(buf, format=fmt)
    return buf.getvalue()


async def extract_drug_names(image_bytes: bytes) -> tuple[list[str], list[str]]:
    """
    Claude Vision으로 이미지에서 약 이름 추출 후 RapidFuzz 정규화.
    Returns: (ocr_raw, normalized)
    """
    resized = _resize_image(image_bytes)
    b64 = base64.standard_b64encode(resized).decode("utf-8")

    try:
        message = await _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            timeout=10,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": VISION_PROMPT},
                    ],
                }
            ],
        )
        usage = message.usage
        logger.info(
            f"Vision OCR 토큰 사용: input={usage.input_tokens} output={usage.output_tokens}"
        )
        raw_text = message.content[0].text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        data = json.loads(raw_text.strip())
        ocr_raw = [name.strip() for name in data.get("drug_names", []) if name.strip()]
    except Exception as e:
        logger.warning(f"Vision OCR 실패: {e}")
        return [], []

    logger.info(f"Vision OCR 추출 결과: {ocr_raw}")

    # RapidFuzz로 공식 품목명 정규화
    normalized = []
    for text in ocr_raw:
        matched = await normalize_drug_name(text)
        if matched and matched not in normalized:
            normalized.append(matched)

    return ocr_raw, normalized


async def normalize_drug_name(raw_text: str) -> Optional[str]:
    """
    DRUG-03: RapidFuzz token_sort_ratio로 공식 품목명 정규화.
    유사도 80% 이상만 허용.
    """
    if not raw_text or not raw_text.strip():
        return None

    db = get_db()
    rows = await db.fetch("SELECT drug_id, official_name FROM drug_names")

    best_score = 0
    best_name = None

    for row in rows:
        score = max(
            fuzz.token_sort_ratio(raw_text, row["official_name"]),
            fuzz.partial_ratio(raw_text, row["official_name"]),
        )
        if score > best_score:
            best_score = score
            best_name = row["official_name"]

    logger.info(f"DRUG-03 정규화: '{raw_text}' → '{best_name}' ({best_score}%)")
    if best_score >= 80:
        return best_name
    return None
