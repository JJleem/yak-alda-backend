import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routers import drugs, interaction
# from app.routers import ocr  # OCR: 메모리 이슈로 임시 비활성화
from app.core.redis import init_redis, close_redis
from app.core.database import init_db, close_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("서버 시작 — Redis, DB 초기화 중...")
    await init_redis()
    await init_db()
    logger.info("초기화 완료")
    yield
    await close_redis()
    await close_db()
    logger.info("서버 종료")


app = FastAPI(
    title="약;알다 API",
    description="의약품 정보 조회 · OCR 분석 · 병용금기 확인 서비스",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 배포 후 프론트 도메인으로 교체
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(drugs.router, prefix="/api/v1/drugs", tags=["drugs"])
# app.include_router(ocr.router, prefix="/api/v1/ocr", tags=["ocr"])  # OCR: 메모리 이슈로 임시 비활성화
app.include_router(interaction.router, prefix="/api/v1/drugs", tags=["interaction"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": "서버 내부 오류가 발생했습니다."},
    )


@app.get("/health")
async def health_check():
    from app.core.redis import get_redis
    from app.core.database import get_db

    redis_ok = False
    db_ok = False

    try:
        await get_redis().ping()
        redis_ok = True
    except Exception:
        pass

    try:
        await get_db().fetchval("SELECT 1")
        db_ok = True
    except Exception:
        pass

    status = "ok" if redis_ok and db_ok else "degraded"
    return {"status": status, "redis": redis_ok, "db": db_ok}
