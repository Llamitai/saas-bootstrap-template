from dataclasses import dataclass

from src.auth.application.use_cases.mixins import TenantSessionMixin
from src.common.domain.buses.queries import QueryBus
from src.common.domain.entities.auth.user_session import TenantUserProfile
from src.common.domain.interfaces.use_case import UseCase
from src.common.domain.models.user import User


@dataclass
class TenantUserProfileBuilder(TenantSessionMixin, UseCase):
    user: User
    query_bus: QueryBus

    async def execute(self) -> TenantUserProfile:
        tenant = await self._get_tenant(user_id=self.user.uuid)
        tenant_user = await self._get_tenant_user(user=self.user, tenant=tenant)
        tenant_role = tenant_user.tenant_role_meta if tenant_user else None

        return TenantUserProfile(
            user=self.user,
            tenant=tenant,
            tenant_role=tenant_role,
        )
