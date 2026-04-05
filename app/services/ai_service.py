import json
import logging
from typing import Optional
import anthropic
from app.core.config import ANTHROPIC_API_KEY
from app.models.drug import AITranslation

logger = logging.getLogger(__name__)

_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = (
    "당신은 약사입니다. 중학생도 이해할 수 있게 설명하세요. "
    "진단·처방 의견은 절대 하지 마세요. "
    "반드시 아래 JSON 형식으로만 응답하세요:\n"
    '{"summary":"...","effect_simple":"...","caution_simple":"...","side_effect_simple":"...","dosage_simple":"..."}'
)


async def translate_drug_info(raw_data: dict) -> Optional[AITranslation]:
    """식약처 원문을 쉬운 말로 변환. 실패 시 None 반환 → 호출부에서 fallback 처리."""
    user_prompt = f"다음 의약품 정보를 쉽게 설명해주세요:\n{json.dumps(raw_data, ensure_ascii=False)}"

    for attempt in range(2):  # 최대 2회 시도
        try:
            message = await _client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                timeout=15,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            usage = message.usage
            logger.info(
                f"AI-01 토큰 사용: input={usage.input_tokens} output={usage.output_tokens} "
                f"(attempt {attempt+1})"
            )
            raw_text = message.content[0].text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
            result = json.loads(raw_text.strip())
            logger.info("AI 변환 성공")
            return AITranslation(**result)
        except Exception as e:
            logger.warning(f"AI 변환 실패 (attempt {attempt+1}): {e}")
            if attempt == 1:
                return None

    return None
