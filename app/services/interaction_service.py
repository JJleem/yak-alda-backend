import json
from typing import List, Optional
import httpx
from app.core.config import SERVICE_KEY
from app.core.redis import get_redis
from app.core.database import get_db
from app.models.drug import InteractionResponse, DrugRef
from app.services.ai_service import translate_drug_info

DUR_BASE = "http://apis.data.go.kr/1471000/DURPrdlstInfoService03"
INTERACTION_CACHE_TTL = 60 * 60 * 24 * 7  # 7일


async def check_interaction(drug_ids: List[str]) -> Optional[InteractionResponse]:
    """
    병용금기 확인 메인 로직.
    drug_ids는 2개 이상 필수.
    """
    db = get_db()
    redis = get_redis()

    # 1. 각 drug_id 유효성 확인 + 이름 조회
    drugs = []
    for drug_id in drug_ids:
        row = await db.fetchrow("SELECT drug_id, name FROM drugs WHERE drug_id = $1", drug_id)
        if row is None:
            return None  # 유효하지 않은 drug_id → 호출부에서 400 처리
        drugs.append(DrugRef(drug_id=row["drug_id"], name=row["name"]))

    # 2. 오름차순 정렬 후 조합 키 생성
    sorted_ids = sorted(drug_ids)
    cache_key = f"interaction:{':'.join(sorted_ids)}"

    # 3. Redis 캐시 확인
    cached = await redis.get(cache_key)
    if cached:
        return InteractionResponse(**json.loads(cached))

    # 4. DUR API 병용금기 교차 비교
    conflicts = []
    for i, id_a in enumerate(sorted_ids):
        forbidden_map = await _fetch_contraindications(id_a)
        for id_b in sorted_ids[i + 1:]:
            if id_b in forbidden_map:
                conflicts.append(forbidden_map[id_b])

    # 5. 결과 판정
    if conflicts:
        result = "forbidden"
        level = "danger"
        official_raw = "\n".join(
            c.get("PROHBT_CONTENT", "") for c in conflicts if c.get("PROHBT_CONTENT")
        ) or None
    else:
        result = "safe"
        level = "safe"
        official_raw = None

    # 6. forbidden이면 AI 변환
    result_simple = None
    if result == "forbidden" and official_raw:
        translation = await translate_drug_info({"interaction_raw": official_raw})
        if translation:
            result_simple = translation.effect_simple  # 병용금기 설명은 effect_simple 필드 활용

    # 7. DB 저장
    await db.execute(
        """
        INSERT INTO interactions (drug_id_1, drug_id_2, result, level, official_raw, result_simple)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (drug_id_1, drug_id_2) DO UPDATE SET
            result = EXCLUDED.result,
            level = EXCLUDED.level,
            official_raw = EXCLUDED.official_raw,
            result_simple = EXCLUDED.result_simple
        """,
        sorted_ids[0],
        sorted_ids[1],
        result,
        level,
        official_raw,
        result_simple,
    )

    # 8. 응답 생성 + Redis 저장
    response = InteractionResponse(
        drugs=drugs,
        result=result,
        level=level,
        result_simple=result_simple,
        official_raw=official_raw,
    )
    await redis.setex(cache_key, INTERACTION_CACHE_TTL, response.model_dump_json())

    return response


async def _fetch_contraindications(item_seq: str) -> dict:
    """특정 약의 병용금기 목록 조회. {MIXTURE_ITEM_SEQ: item} 딕셔너리 반환."""
    url = f"{DUR_BASE}/getUsjntTabooInfoList03"
    params = {
        "serviceKey": SERVICE_KEY,
        "itemSeq": item_seq,
        "numOfRows": 100,
        "type": "json",
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = data.get("body", {}).get("items") or []
    return {item["MIXTURE_ITEM_SEQ"]: item for item in items if item.get("MIXTURE_ITEM_SEQ")}
