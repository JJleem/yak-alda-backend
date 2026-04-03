from fastapi import APIRouter, HTTPException
from app.models.drug import InteractionRequest
from app.services.interaction_service import check_interaction

router = APIRouter()


@router.post("/interaction")
async def check_interaction_endpoint(body: InteractionRequest):
    if len(body.drug_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail={"code": "INSUFFICIENT_DRUGS", "message": "drug_ids는 2개 이상 필요합니다."},
        )

    result = await check_interaction(body.drug_ids)
    if result is None:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_DRUG_ID", "message": "유효하지 않은 drug_id가 포함되어 있습니다."},
        )

    return result
