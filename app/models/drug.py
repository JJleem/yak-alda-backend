from typing import Optional, List
from pydantic import BaseModel


class OfficialRaw(BaseModel):
    effect: Optional[str] = None
    caution: Optional[str] = None
    side_effect: Optional[str] = None


class DrugDetailResponse(BaseModel):
    drug_id: str
    name: str
    manufacturer: Optional[str] = None
    summary: Optional[str] = None
    effect_simple: Optional[str] = None
    caution_simple: Optional[str] = None
    side_effect_simple: Optional[str] = None
    dosage_simple: Optional[str] = None
    official_raw: OfficialRaw
    disclaimer: str = "이 정보는 참고용이며 진단·처방을 대체하지 않습니다. 복용 전 전문가와 상담하세요."


class AITranslation(BaseModel):
    summary: str
    effect_simple: str
    caution_simple: str
    side_effect_simple: str
    dosage_simple: str


class DrugSearchItem(BaseModel):
    drug_id: str
    name: str
    manufacturer: Optional[str] = None
    summary: Optional[str] = None
    relevance_score: float


class DrugSearchResponse(BaseModel):
    query: str
    total: int
    page: int
    total_pages: int
    results: List[DrugSearchItem]
