from fastapi import HTTPException


class UpstreamError(HTTPException):
    def __init__(self, detail: str = "외부 API 호출에 실패했습니다."):
        super().__init__(
            status_code=502,
            detail={"code": "UPSTREAM_ERROR", "message": detail},
        )


class TimeoutError(HTTPException):
    def __init__(self, detail: str = "요청 처리 시간이 초과됐습니다."):
        super().__init__(
            status_code=504,
            detail={"code": "TIMEOUT", "message": detail},
        )
