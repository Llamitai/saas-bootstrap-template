from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessChecks(BaseModel):
    database: Literal["ok", "error"]
    redis: Literal["ok", "error"]


class ReadinessResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    checks: ReadinessChecks
