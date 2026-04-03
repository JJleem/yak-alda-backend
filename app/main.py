from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.routers import drugs, ocr, interaction
from app.core.redis import init_redis, close_redis
from app.core.database import init_db, close_db
from app.services.ocr_service import get_reader


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    await init_db()
    get_reader()  # EasyOCR 모델 미리 로드
    yield
    await close_redis()
    await close_db()


app = FastAPI(
    title="약;알다 API",
    description="의약품 정보 조회 · OCR 분석 · 병용금기 확인 서비스",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(drugs.router, prefix="/api/v1/drugs", tags=["drugs"])
app.include_router(ocr.router, prefix="/api/v1/ocr", tags=["ocr"])
app.include_router(interaction.router, prefix="/api/v1/drugs", tags=["interaction"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": "서버 내부 오류가 발생했습니다."},
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}
