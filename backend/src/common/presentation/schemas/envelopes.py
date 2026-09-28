from datetime import datetime
from typing import Generic, TypeVar

from src.common.domain.enums.common import TaskStatus
from src.common.presentation.schemas.base import ApiSchema

T = TypeVar("T")


class PaginationResponse(ApiSchema):
    next_cursor: str | None
    limit: int | None


class Envelope(ApiSchema, Generic[T]):
    """`{data, timestamp}`: every successful ApiJSONResponse."""

    data: T
    timestamp: datetime


class PageEnvelope(ApiSchema, Generic[T]):
    """`{data, pagination, timestamp}`: ApiJSONResponse rendering a cursor `Page`."""

    data: list[T]
    pagination: PaginationResponse
    timestamp: datetime


class TaskResultResponse(ApiSchema):
    status: TaskStatus
    message: str | None = None


class StatusResponse(ApiSchema):
    status: str


class MessageResponse(ApiSchema):
    message: str


class PermissionResponse(ApiSchema):
    code: str
    label: str


class EmailResponse(ApiSchema):
    email: str


class AcceptedResponse(ApiSchema):
    accepted: bool
