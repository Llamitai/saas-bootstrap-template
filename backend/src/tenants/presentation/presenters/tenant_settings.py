from dataclasses import dataclass
from typing import Any

from src.common.domain.interfaces.presenter import Presenter
from src.common.domain.models.tenants.tenant import Tenant


@dataclass
class TenantSettingsPresenter(Presenter[Tenant]):
    instance: Tenant

    @property
    def to_dict(self) -> dict[str, Any]:
        return {
            "uuid": str(self.instance.uuid),
            "name": self.instance.name,
            "tenant_id": self.instance.slug,
            "avatar": self.instance.logo_url,
        }
