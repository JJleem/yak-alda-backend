"""
식약처 공공 API 사용 예시 (MediKnow 백엔드 참고용)

실제 서비스 코드가 아닌 개념 확인용 예시입니다.
FastAPI 라우터에서 사용할 때는 httpx (async) 권장.
"""

import requests

SERVICE_KEY = "여기에_공공데이터포털_발급키_입력"  # URL encode 불필요 (requests가 자동 처리)

# =============================================================================
# EXT-01 · 식약처 e약은요 API
# 용도: 약 이름 검색 / 품목기준코드로 상세 정보 조회
# Base URL: http://apis.data.go.kr/1471000/DrbEasyDrugInfoService
# =============================================================================

BASE_URL_EXT01 = "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"

# --- 예시 1-A: 약 이름으로 검색 (DRUG-01) ---
def search_drug_by_name(item_name: str, page: int = 1, limit: int = 10):
    params = {
        "serviceKey": SERVICE_KEY,
        "itemName": item_name,   # 부분 검색 가능 (예: "타이레놀" → "타이레놀500mg" 포함)
        "pageNo": page,
        "numOfRows": limit,
        "type": "json",          # 반드시 명시 (기본값 XML)
    }
    response = requests.get(BASE_URL_EXT01, params=params)
    data = response.json()

    # 응답 구조: data["body"]["items"] → 약 목록
    items = data["body"]["items"]
    return items

# 호출 예시
# results = search_drug_by_name("타이레놀")
# → [{"itemName": "타이레놀500mg정", "itemSeq": "200212435", "efcyQesitm": "...", ...}, ...]


# --- 예시 1-B: 품목기준코드로 단일 약 상세 조회 (DRUG-02) ---
def get_drug_detail_by_seq(item_seq: str):
    params = {
        "serviceKey": SERVICE_KEY,
        "itemSeq": item_seq,     # 정확한 코드 → 결과 1건
        "type": "json",
    }
    response = requests.get(BASE_URL_EXT01, params=params)
    data = response.json()

    items = data["body"]["items"]
    if not items:
        return None
    return items[0]  # 코드 검색이므로 항상 1건

# 호출 예시
# detail = get_drug_detail_by_seq("200212435")
# → {
#     "itemName": "타이레놀500mg정",
#     "itemSeq": "200212435",
#     "entpName": "한국얀센(주)",
#     "efcyQesitm": "이 약은 두통, 치통, 발열 시의 해열 등에 쓰입니다.",  → AI-01 변환 원본
#     "useMethodQesitm": "성인 1회 1~2정, 1일 3~4회 ...",               → AI-01 변환 원본
#     "atpnQesitm": "다음 사람은 이 약을 복용하지 마십시오 ...",          → AI-01 변환 원본
#     "seQesitm": "구역, 구토, 복통이 나타날 수 있습니다.",               → AI-01 변환 원본
#     "depositMethodQesitm": "밀봉용기, 실온(1~30℃)에 보관하십시오.",
#     "itemImage": "https://..."
#   }


# =============================================================================
# EXT-02 · 식약처 낱알식별 API
# 용도: 알약 모양 · 색상 · 각인으로 후보 약 목록 조회
# Base URL: http://apis.data.go.kr/1471000/MdcinGrnIdntfcInfoService03
# =============================================================================

BASE_URL_EXT02 = "http://apis.data.go.kr/1471000/MdcinGrnIdntfcInfoService03/getMdcinGrnIdntfcInfoList03"

# --- 예시 2: 모양 + 색상 + 각인으로 알약 검색 ---
def search_pill_by_shape(
    shape: str = None,      # 예: "원형", "타원형", "장방형"
    color: str = None,      # 예: "하양", "노랑", "분홍"
    print_front: str = None,  # 예: "500", "T", "ER"
    print_back: str = None,
    page: int = 1,
    limit: int = 10,
):
    params = {
        "serviceKey": SERVICE_KEY,
        "pageNo": page,
        "numOfRows": limit,
        "type": "json",
    }
    # 입력된 파라미터만 추가 (None이면 생략)
    if shape:       params["DRUG_SHAPE"] = shape
    if color:       params["COLOR_CLASS1"] = color
    if print_front: params["PRINT_FRONT"] = print_front
    if print_back:  params["PRINT_BACK"] = print_back

    response = requests.get(BASE_URL_EXT02, params=params)
    data = response.json()

    items = data["body"]["items"]
    return items

# 호출 예시
# candidates = search_pill_by_shape(shape="원형", color="하양", print_front="500")
# → [
#     {
#       "ITEM_SEQ": "200212435",
#       "ITEM_NAME": "타이레놀500mg정",
#       "ENTP_NAME": "한국얀센(주)",
#       "DRUG_SHAPE": "원형",
#       "COLOR_CLASS1": "하양",
#       "PRINT_FRONT": "TYLENOL",
#       "PRINT_BACK": "500",
#       "ITEM_IMAGE": "https://nedrug.mfds.go.kr/...",
#       "CLASS_NAME": "해열.진통.소염제",
#       "ETC_OTC_NAME": "일반의약품"
#     },
#     ...  # 조건에 맞는 후보 목록
#   ]

# 앱 흐름:
# 사용자가 후보 목록에서 약 선택
# → 선택한 ITEM_SEQ로 get_drug_detail_by_seq() 호출 (EXT-01)
# → 상세 정보 화면으로 이동


# =============================================================================
# EXT-03 · 식약처 DUR 품목정보 API
# 용도: 병용금기 / 임부금기 / 특정연령대금기 조회
# Base URL: http://apis.data.go.kr/1471000/DURPrdlstInfoService03
# =============================================================================

BASE_URL_EXT03 = "http://apis.data.go.kr/1471000/DURPrdlstInfoService03"

# --- 예시 3-A: 병용금기 조회 ---
def get_contraindication(item_seq: str):
    """특정 약의 병용금기 목록 조회 (함께 먹으면 안 되는 약 코드 목록)"""
    url = f"{BASE_URL_EXT03}/getUsjntTabooInfoList03"
    params = {
        "serviceKey": SERVICE_KEY,
        "itemSeq": item_seq,
        "numOfRows": 100,  # 금기 목록 전체 가져오기
        "type": "json",
    }
    response = requests.get(url, params=params)
    data = response.json()

    items = data["body"]["items"] or []
    # MIXTURE_ITEM_SEQ: 이 약과 함께 먹으면 안 되는 약의 품목기준코드
    return items

# --- 예시 3-B: 임부금기 조회 ---
def get_pregnancy_taboo(item_seq: str):
    url = f"{BASE_URL_EXT03}/getPwnmTabooInfoList03"
    params = {
        "serviceKey": SERVICE_KEY,
        "itemSeq": item_seq,
        "numOfRows": 100,
        "type": "json",
    }
    response = requests.get(url, params=params)
    data = response.json()
    return data["body"]["items"] or []

# --- 예시 3-C: 특정연령대금기 조회 ---
def get_age_taboo(item_seq: str):
    url = f"{BASE_URL_EXT03}/getSpcifyAgrdeTabooInfoList03"
    params = {
        "serviceKey": SERVICE_KEY,
        "itemSeq": item_seq,
        "numOfRows": 100,
        "type": "json",
    }
    response = requests.get(url, params=params)
    data = response.json()
    return data["body"]["items"] or []


# =============================================================================
# INTERACTION-01 핵심 로직 — 병용금기 교차 비교
# =============================================================================

def check_drug_interaction(drug_seq_list: list[str]) -> dict:
    """
    약 2개 이상의 품목기준코드를 받아 병용금기 여부 확인.

    흐름:
      약 A의 병용금기 목록 조회 → MIXTURE_ITEM_SEQ 추출
      → 약 B, C, ... 의 코드가 목록에 있으면 병용금기 확정
    """
    conflicts = []

    for i, seq_a in enumerate(drug_seq_list):
        contraindication_list = get_contraindication(seq_a)

        # 병용금기 상대 코드 목록
        forbidden_seqs = {
            item["MIXTURE_ITEM_SEQ"]: item
            for item in contraindication_list
        }

        # 나머지 약들과 교차 비교
        for seq_b in drug_seq_list[i + 1:]:
            if seq_b in forbidden_seqs:
                matched = forbidden_seqs[seq_b]
                conflicts.append({
                    "drug_a_seq": seq_a,
                    "drug_b_seq": seq_b,
                    "drug_b_name": matched.get("MIXTURE_ITEM_NAME"),
                    "reason_raw": matched.get("PROHBT_CONTENT"),  # → AI-01로 쉬운 말 변환
                })

    return {
        "has_conflict": len(conflicts) > 0,
        "conflicts": conflicts,
    }

# 호출 예시
# result = check_drug_interaction(["200212435", "197000013"])
# → {
#     "has_conflict": True,
#     "conflicts": [
#       {
#         "drug_a_seq": "200212435",
#         "drug_b_seq": "197000013",
#         "drug_b_name": "아스피린장용정",
#         "reason_raw": "아세트아미노펜과 아스피린 병용 시 간독성 위험 증가 ..."
#         # → AI-01에 전달 → "두 약을 함께 드시면 간에 무리가 갈 수 있어요."
#       }
#     ]
#   }
#
# has_conflict: False 이면 → "함께 복용해도 괜찮아요" 표시
