from typing import Annotated

from fastapi import Depends, Header

from src.common.application.logging import get_logger
from src.common.domain.exceptions.tenants import TenantNotFoundError
from src.common.domain.exceptions.users import TenantUserRequiredError
from src.common.domain.models.tenants.tenant import Tenant
from src.common.domain.models.tenants.tenant_user import TenantUser
from src.common.infrastructure.dependencies.common import DomainContextDep
from src.common.infrastructure.dependencies.session import AuthenticatedUserDep

logger = get_logger(__name__)


async def get_tenant(
    domain_context: DomainContextDep,
    tenant_slug: Annotated[str | None, Header(alias="X-Tenant")] = None,
) -> Tenant | None:
    if not tenant_slug or not tenant_slug.strip():
        return None

    return await domain_context.tenant_repository.find_by_slug(tenant_slug=tenant_slug.strip())


TenantDep = Annotated[Tenant | None, Depends(get_tenant)]


async def get_required_tenant(
    domain_context: DomainContextDep,
    tenant_slug: Annotated[str | None, Header(alias="X-Tenant")] = None,
) -> Tenant:
    if not tenant_slug or not tenant_slug.strip():
        logger.warning("tenant.header_required")
        raise TenantNotFoundError

    slug = tenant_slug.strip()
    tenant = await domain_context.tenant_repository.find_by_slug(slug)
    if not tenant:
        logger.warning("tenant.not_found", tenant_slug=slug)
        raise TenantNotFoundError

    return tenant


RequiredTenantDep = Annotated[Tenant, Depends(get_required_tenant)]


async def get_tenant_user(
    user: AuthenticatedUserDep,
    domain_context: DomainContextDep,
    tenant: RequiredTenantDep,
) -> TenantUser | None:
    tenant_user = await domain_context.tenant_user_repository.find_by_args(
        user_id=user.uuid,
        tenant_id=tenant.uuid,
    )
    if tenant_user:
        tenant_user.tenant = tenant
    return tenant_user


TenantUserDep = Annotated[TenantUser | None, Depends(get_tenant_user)]


async def get_required_tenant_user(
    user: AuthenticatedUserDep,
    domain_context: DomainContextDep,
    tenant: RequiredTenantDep,
) -> TenantUser:
    tenant_user = await domain_context.tenant_user_repository.find_by_args(
        user_id=user.uuid,
        tenant_id=tenant.uuid,
    )
    if not tenant_user:
        raise TenantUserRequiredError
    tenant_user.tenant = tenant
    return tenant_user


RequiredTenantUserDep = Annotated[TenantUser, Depends(get_required_tenant_user)]


def required_tenant_for(tenant_user: TenantUser) -> Tenant:
    if tenant_user.tenant is None:
        raise TenantNotFoundError(str(tenant_user.tenant_id))
    return tenant_user.tenant
