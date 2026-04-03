import asyncio
from fastapi import APIRouter, HTTPException, Query
from app.services.drug_service import get_drug_detail, search_drugs
from app.core.exceptions import TimeoutError

router = APIRouter()


@router.get("/search")
async def search_drugs_endpoint(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=30),
):
    results = await search_drugs(q, page, limit)
    if results.total == 0:
        raise HTTPException(status_code=404, detail={"code": "NO_RESULT", "message": "검색 결과가 없습니다."})
    return results


@router.get("/{drug_id}")
async def get_drug_detail_endpoint(drug_id: str):
    try:
        result = await asyncio.wait_for(get_drug_detail(drug_id), timeout=20.0)
    except asyncio.TimeoutError:
        raise TimeoutError()
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "DRUG_NOT_FOUND", "message": "해당 약을 찾을 수 없습니다."})
    return result
