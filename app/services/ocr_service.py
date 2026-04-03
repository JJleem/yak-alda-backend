import io
import numpy as np
from PIL import Image
from rapidfuzz import fuzz
from typing import Optional
import easyocr
from app.core.database import get_db

# 서버 시작 시 1회 초기화 (한국어+영어)
_reader: Optional[easyocr.Reader] = None


def get_reader() -> easyocr.Reader:
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["ko", "en"], gpu=False)
    return _reader


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """
    EasyOCR 정확도 향상을 위한 이미지 전처리.
    그레이스케일 → 리사이즈 (최대 1280px) → 이진화
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("L")  # 그레이스케일

    # 리사이즈 (최대 1280px)
    max_size = 1280
    w, h = img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    # 이진화 (threshold 128)
    img = img.point(lambda x: 0 if x < 128 else 255, "1").convert("L")

    return np.array(img)


async def extract_drug_names(image_bytes: bytes) -> tuple[list[str], list[str]]:
    """
    이미지에서 텍스트 추출 후 약 이름 정규화.
    Returns: (ocr_raw, normalized)
    """
    # OCR 텍스트 추출
    img_array = preprocess_image(image_bytes)
    reader = get_reader()
    results = reader.readtext(img_array, detail=0)  # 텍스트만 추출
    ocr_raw = [text.strip() for text in results if text.strip()]
    print(f"[OCR] 추출 결과: {ocr_raw}")

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

    print(f"[DRUG-03] '{raw_text}' → '{best_name}' ({best_score}%)")
    if best_score >= 80:
        return best_name
    return None
