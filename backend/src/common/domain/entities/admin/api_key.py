from typing import Any
from uuid import UUID

from pydantic import Field

from src.common.domain.entities.mixins.common import BaseModelMixin, TimestampMixin


class ApiKey(
    BaseModelMixin,
    TimestampMixin,
):
    name: str
    key_prefix: str | None = Field(default=None)
    key_hash: str
    permissions: list[str] = Field(default_factory=list)
    is_revoked: bool = Field(default=False)
    tenant_ids: list[UUID] | None = Field(default=None)

    @property
    def is_active(self) -> bool:
        return not self.is_revoked

    @property
    def is_general_scope(self) -> bool:
        return not self.tenant_ids

    def has_permissions(self, permissions: list[str]) -> bool:
        if not self.is_active:
            return False
        return all(permission in self.permissions for permission in permissions)

    def allows_tenant(self, tenant_id: UUID | None) -> bool:
        return self.allows_tenants([tenant_id] if tenant_id is not None else None)

    def allows_tenants(self, tenant_ids: list[UUID] | None) -> bool:
        if self.tenant_ids is None:
            return True
        if not tenant_ids:
            return False
        return set(tenant_ids).issubset(self.tenant_ids)

    @property
    def to_persist_dict(self) -> dict[str, Any]:

        return {
            "tenants": ([str(tenant_id) for tenant_id in self.tenant_ids] if self.tenant_ids is not None else None),
            "name": self.name,
            "key_prefix": self.key_prefix,
            "key_hash": self.key_hash,
            "permissions": list(self.permissions),
            "is_revoked": self.is_revoked,
        }
