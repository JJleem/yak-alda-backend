from fastapi import APIRouter, HTTPException, UploadFile, File
from app.models.drug import OCRResponse
from app.services.ocr_service import extract_drug_names
from app.services.drug_service import get_drug_detail, search_drugs

router = APIRouter()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/heic"}
MAX_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/analyze")
async def analyze_ocr(image: UploadFile = File(...)):
    # 파일 형식 검증
    if image.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_FILE_TYPE", "message": "jpg, png, heic 파일만 지원합니다."},
        )

    image_bytes = await image.read()

    # 파일 크기 검증
    if len(image_bytes) > MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail={"code": "IMAGE_TOO_LARGE", "message": "이미지 크기는 10MB 이하여야 합니다."},
        )

    # OCR 추출 + 정규화
    ocr_raw, normalized = await extract_drug_names(image_bytes)

    if not ocr_raw:
        raise HTTPException(
            status_code=422,
            detail={"code": "OCR_FAILED", "message": "이미지에서 텍스트를 추출할 수 없습니다."},
        )

    # 정규화 결과 없으면 OCR 텍스트 직접 사용 (fallback)
    search_terms = normalized if normalized else ocr_raw

    # 약 상세 조회
    drugs = []
    seen_ids = set()
    for term in search_terms:
        search_result = await search_drugs(term, page=1, limit=1)
        if search_result.results:
            drug_id = search_result.results[0].drug_id
            if drug_id not in seen_ids:
                seen_ids.add(drug_id)
                detail = await get_drug_detail(drug_id)
                if detail:
                    drugs.append(detail)

    if not drugs:
        raise HTTPException(
            status_code=404,
            detail={"code": "NO_DRUG_FOUND", "message": "약 정보를 찾을 수 없습니다."},
        )

    return OCRResponse(ocr_raw=ocr_raw, normalized=normalized, drugs=drugs)
