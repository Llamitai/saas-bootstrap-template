from fastapi import APIRouter, Depends

from src.auth.presentation.endpoints.google_login import google_login
from src.auth.presentation.endpoints.login import login
from src.auth.presentation.endpoints.logout import logout
from src.auth.presentation.endpoints.refresh import refresh
from src.auth.presentation.endpoints.reset_password import reset_password
from src.auth.presentation.endpoints.reset_password_confirm import (
    reset_password_confirm,
)
from src.auth.presentation.endpoints.session import session
from src.common.infrastructure.dependencies.rate_limit import create_rate_limit_dependency

auth_router = router = APIRouter(prefix="/auth", tags=["auth"])

# Per-IP rate limits for credential-sensitive endpoints. Template defaults:
# generous enough for real users (and the E2E suite), tight enough to slow
# down brute-force and token-guessing attempts.
login_rate_limit = create_rate_limit_dependency(limit=20, window=60)
refresh_rate_limit = create_rate_limit_dependency(limit=30, window=60)
reset_password_rate_limit = create_rate_limit_dependency(limit=5, window=60)
reset_password_confirm_rate_limit = create_rate_limit_dependency(limit=5, window=60)


auth_router.add_api_route(
    path="/login",
    endpoint=login,
    methods=["POST"],
    dependencies=[Depends(login_rate_limit)],
)
auth_router.add_api_route(
    path="/google-login",
    endpoint=google_login,
    methods=["POST"],
)
auth_router.add_api_route(
    path="/reset-password",
    endpoint=reset_password,
    methods=["POST"],
    dependencies=[Depends(reset_password_rate_limit)],
)
auth_router.add_api_route(
    path="/reset-password/confirm",
    endpoint=reset_password_confirm,
    methods=["POST"],
    dependencies=[Depends(reset_password_confirm_rate_limit)],
)
auth_router.add_api_route(
    path="/refresh",
    endpoint=refresh,
    methods=["POST"],
    dependencies=[Depends(refresh_rate_limit)],
)
auth_router.add_api_route(
    path="/logout",
    endpoint=logout,
    methods=["POST"],
)

# -> Session Configuration

auth_router.add_api_route(
    path="/session",
    endpoint=session,
    methods=["GET"],
)
