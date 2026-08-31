from uuid import UUID

from src.common.database.models.admin.api_key import ApiKeyORM
from src.common.domain.entities.admin.api_key import ApiKey
from src.common.domain.exceptions.permission import InvalidApiKeyScopeError


def parse_tenant_ids(tenants: object) -> list[UUID] | None:
    if tenants is None:
        return None

    if not isinstance(tenants, list):
        raise InvalidApiKeyScopeError(context={"reason": "tenants must be a list"})

    tenant_ids: list[UUID] = []

    for tenant_id in tenants:
        if not isinstance(tenant_id, str):
            raise InvalidApiKeyScopeError(
                context={
                    "reason": "tenant_id must be a string",
                    "value_type": type(tenant_id).__name__,
                }
            )

        try:
            tenant_ids.append(UUID(tenant_id))
        except ValueError as exc:
            raise InvalidApiKeyScopeError(
                context={
                    "reason": "invalid tenant UUID",
                    "tenant_id": tenant_id,
                }
            ) from exc

    return tenant_ids


def build_api_key(orm_instance: ApiKeyORM) -> ApiKey:

    return ApiKey(
        uuid=orm_instance.uuid,
        tenant_ids=parse_tenant_ids(orm_instance.tenants),
        name=orm_instance.name,
        key_prefix=orm_instance.key_prefix,
        key_hash=orm_instance.key_hash,
        permissions=orm_instance.permissions,
        is_revoked=orm_instance.is_revoked,
        created_at=orm_instance.created_at,
        updated_at=orm_instance.updated_at,
    )
