from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from src.common.database.mixins.common import Base, UUIDTimestampMixin


class ApiKeyORM(Base, UUIDTimestampMixin):
    __tablename__ = "admin_api_keys"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    key_prefix: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        unique=True,
        index=True,
    )
    key_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    permissions: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    tenants: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="List of tenant IDs this API key can access. If null, it has access to all tenants.",
    )
