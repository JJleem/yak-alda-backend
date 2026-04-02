from fastapi import APIRouter

router = APIRouter()


@router.post("/analyze")
def analyze_ocr():
    # TODO: OCR-01 구현
    return {"message": "ocr analyze — coming soon"}
