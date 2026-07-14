from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.database.mixins.common import Base, UUIDTimestampMixin
from src.common.domain.enums.countries import CountryIsoCode
from src.common.domain.enums.currencies import CurrencyCode
from src.common.domain.enums.locales import TimeZone
from src.common.domain.enums.tenants import TenantStatus

if TYPE_CHECKING:
    from src.common.database.models.user import UserORM


class TenantORM(Base, UUIDTimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(25),
        nullable=False,
        default=str(TenantStatus.PENDING),
        comment="Status",
    )
    time_zone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=str(TimeZone.MEXICO_CITY),
    )
    country_code: Mapped[str] = mapped_column(
        String(25),
        nullable=False,
        default=str(CountryIsoCode.MEXICO),
    )
    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default=str(CurrencyCode.MXN),
    )
    logo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        default=None,
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )

    # -> Foreign key
    owner_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "users.uuid",
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
    )

    # Relationship
    owner: Mapped[UserORM | None] = relationship(
        foreign_keys="[TenantORM.owner_id]",
        back_populates=None,
    )

    @property
    def is_active(self) -> bool:
        return self.status == TenantStatus.ACTIVE

    @property
    def display_owner(self) -> str:
        if self.owner:
            return str(self.owner)
        return "No owner"

    def __repr__(self) -> str:
        return f"<Tenant {self.name} ({self.slug})>"

    def __str__(self) -> str:
        return self.name
