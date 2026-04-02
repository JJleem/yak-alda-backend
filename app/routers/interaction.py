from fastapi import APIRouter

router = APIRouter()


@router.post("/interaction")
def check_interaction():
    # TODO: INTERACTION-01 구현
    return {"message": "interaction check — coming soon"}
