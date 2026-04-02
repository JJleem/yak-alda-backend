from fastapi import APIRouter

router = APIRouter()


@router.get("/search")
def search_drugs(q: str, page: int = 1, limit: int = 10):
    # TODO: DRUG-01 구현
    return {"message": "drug search — coming soon", "q": q}


@router.get("/{drug_id}")
def get_drug_detail(drug_id: str):
    # TODO: DRUG-02 구현
    return {"message": "drug detail — coming soon", "drug_id": drug_id}
