import json
from typing import Optional
import httpx
from app.core.config import SERVICE_KEY
from app.core.redis import get_redis
from app.core.database import get_db
from app.models.drug import DrugDetailResponse, OfficialRaw
from app.services.ai_service import translate_drug_info

EXT01_URL = "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"
DRUG_CACHE_TTL = 60 * 60 * 24 * 7  # 7일


async def get_drug_detail(drug_id: str) -> Optional[DrugDetailResponse]:
    """
    약 상세 조회 메인 로직.
    Redis → DB → 식약처 API 순서로 조회.
    """
    redis = get_redis()

    # 1. Redis 캐시 확인
    cached = await redis.get(f"drug:{drug_id}")
    if cached:
        return DrugDetailResponse(**json.loads(cached))

    # 2. DB 조회
    db = get_db()
    row = await db.fetchrow("SELECT * FROM drugs WHERE drug_id = $1", drug_id)

    if row is None:
        # 3. 식약처 API 호출
        raw = await _fetch_from_api(drug_id)
        if raw is None:
            return None
        # DB에 저장
        await _save_to_db(db, raw)
        row = await db.fetchrow("SELECT * FROM drugs WHERE drug_id = $1", drug_id)

    # 4. AI 변환 필요 여부 확인 (effect_simple이 NULL이면 호출)
    if row["effect_simple"] is None:
        raw_data = {
            "effect": row["effect_raw"],
            "dosage": row["dosage_raw"],
            "caution": row["caution_raw"],
            "side_effect": row["side_effect_raw"],
        }
        translation = await translate_drug_info(raw_data)
        if translation:
            await db.execute(
                """
                UPDATE drugs SET
                    summary = $1,
                    effect_simple = $2,
                    caution_simple = $3,
                    side_effect_simple = $4,
                    dosage_simple = $5
                WHERE drug_id = $6
                """,
                translation.summary,
                translation.effect_simple,
                translation.caution_simple,
                translation.side_effect_simple,
                translation.dosage_simple,
                drug_id,
            )
            row = await db.fetchrow("SELECT * FROM drugs WHERE drug_id = $1", drug_id)

    # 5. 응답 객체 생성
    response = DrugDetailResponse(
        drug_id=row["drug_id"],
        name=row["name"],
        manufacturer=row["manufacturer"],
        summary=row["summary"],
        effect_simple=row["effect_simple"],
        caution_simple=row["caution_simple"],
        side_effect_simple=row["side_effect_simple"],
        dosage_simple=row["dosage_simple"],
        official_raw=OfficialRaw(
            effect=row["effect_raw"],
            caution=row["caution_raw"],
            side_effect=row["side_effect_raw"],
        ),
    )

    # 6. Redis 캐시 저장
    await redis.setex(f"drug:{drug_id}", DRUG_CACHE_TTL, response.model_dump_json())

    return response


async def _fetch_from_api(drug_id: str) -> Optional[dict]:
    """식약처 e약은요 API에서 약 상세 정보 조회."""
    params = {
        "serviceKey": SERVICE_KEY,
        "itemSeq": drug_id,
        "type": "json",
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(EXT01_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = data.get("body", {}).get("items")
    if not items:
        return None
    return items[0]


async def _save_to_db(db, raw: dict):
    """식약처 API 응답을 drugs 테이블에 저장."""
    caution = " ".join(filter(None, [
        raw.get("atpnWarnQesitm"),
        raw.get("atpnQesitm"),
    ]))
    await db.execute(
        """
        INSERT INTO drugs (drug_id, name, manufacturer, image_url,
            effect_raw, dosage_raw, caution_raw, side_effect_raw,
            interaction_raw, storage_raw)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        ON CONFLICT (drug_id) DO NOTHING
        """,
        raw.get("itemSeq"),
        raw.get("itemName"),
        raw.get("entpName"),
        raw.get("itemImage"),
        raw.get("efcyQesitm"),
        raw.get("useMethodQesitm"),
        caution or None,
        raw.get("seQesitm"),
        raw.get("intrcQesitm"),
        raw.get("depositMethodQesitm"),
    )
