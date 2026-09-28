"""Container probes. Plain JSON (no envelope) so orchestrators can read them directly."""

import asyncio

from fastapi import Request, status
from fastapi.responses import JSONResponse

from src.common.infrastructure.helpers.health import database_is_ready, redis_is_ready


async def health() -> JSONResponse:
    """Liveness: the process answers HTTP. Never touches a dependency."""
    return JSONResponse({"status": "ok"})


async def health_ready(request: Request) -> JSONResponse:
    """Readiness: PostgreSQL answers `SELECT 1` and Redis answers `PING`."""
    state = request.app.state
    database_ok, redis_ok = await asyncio.gather(
        database_is_ready(state.database_config.engine),
        redis_is_ready(state.redis_client),
    )
    ready = database_ok and redis_ok
    return JSONResponse(
        {
            "status": "ok" if ready else "unavailable",
            "checks": {
                "database": "ok" if database_ok else "error",
                "redis": "ok" if redis_ok else "error",
            },
        },
        status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
