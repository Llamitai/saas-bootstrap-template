from fastapi import APIRouter, status

from src.common.presentation.endpoints.health import health, health_ready
from src.common.presentation.endpoints.root import home, sentry_debug
from src.common.presentation.schemas.envelopes import Envelope, MessageResponse, StatusResponse
from src.common.presentation.schemas.health import HealthResponse, ReadinessResponse

common_router = APIRouter()

common_router.add_api_route(
    "/",
    home,
    methods=["GET"],
    summary="API root",
    response_model=Envelope[StatusResponse],
)
common_router.add_api_route(
    "/sentry-debug",
    sentry_debug,
    methods=["GET"],
    summary="Trigger a Sentry test error (local environments only)",
    response_model=MessageResponse,
)

# Container probes: public, no authentication, no rate limit and no envelope.
health_router = APIRouter(prefix="/api/py/health", tags=["health"])
health_router.add_api_route(
    "",
    health,
    methods=["GET"],
    summary="Liveness probe",
    response_model=HealthResponse,
)
health_router.add_api_route(
    "/ready",
    health_ready,
    methods=["GET"],
    summary="Readiness probe (PostgreSQL and Redis)",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
