from fastapi import HTTPException

from src.common.infrastructure.responses.api_json import ApiJSONResponse
from src.common.settings import settings


async def home() -> ApiJSONResponse:
    return ApiJSONResponse(content={"status": "OK"})


async def sentry_debug():
    """Raise on purpose to verify Sentry error tracking. Local environments only."""
    if not settings.ENVIRONMENT.is_local:
        raise HTTPException(
            status_code=404,
            detail="Endpoint only available in development",
        )

    _division_by_zero = 1 / 0  # ty: ignore[division-by-zero]
    return {"message": "This should never be reached"}
