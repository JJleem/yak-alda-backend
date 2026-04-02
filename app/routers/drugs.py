from fastapi import APIRouter, HTTPException
from app.services.drug_service import get_drug_detail

router = APIRouter()


@router.get("/search")
async def search_drugs(q: str, page: int = 1, limit: int = 10):
    # TODO: DRUG-01 구현
    return {"message": "drug search — coming soon", "q": q}


@router.get("/{drug_id}")
async def get_drug_detail_endpoint(drug_id: str):
    result = await get_drug_detail(drug_id)
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "DRUG_NOT_FOUND", "message": "해당 약을 찾을 수 없습니다."})
    return result
