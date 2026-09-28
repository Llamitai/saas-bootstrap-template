"""The profile endpoints render domain model dumps; document them as sent."""

from src.common.domain.models.user import User
from src.common.presentation.schemas.base import camel_schema
from src.common.presentation.schemas.shared import TenantModel

__all__ = ["TenantModel", "UserModel"]


class UserModel(camel_schema(User)):  # ty: ignore[unsupported-base]  generated model
    """`User.model_dump()` as rendered by the profile endpoints."""
