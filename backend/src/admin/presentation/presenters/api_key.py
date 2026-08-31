from dataclasses import dataclass
from typing import Any

from src.common.application.helpers.datetimes import optional_datetime_string
from src.common.domain.entities.admin.api_key import ApiKey
from src.common.domain.interfaces.presenter import Presenter
from src.common.domain.permissions.admin_catalog import admin_permissions_to_list_dict


@dataclass
class ApiKeyPresenter(Presenter[ApiKey]):
    instance: ApiKey

    @property
    def to_dict(self) -> dict[str, Any]:
        return {
            "uuid": str(self.instance.uuid),
            "name": self.instance.name,
            "key_prefix": self.instance.key_prefix,
            "tenant_ids": [str(tenant_id) for tenant_id in self.instance.tenant_ids]
            if self.instance.tenant_ids
            else None,
            "is_general_scope": self.instance.is_general_scope,
            "permissions": admin_permissions_to_list_dict(self.instance.permissions),
            "is_revoked": self.instance.is_revoked,
            "created_at": optional_datetime_string(self.instance.created_at),
            "updated_at": optional_datetime_string(self.instance.updated_at),
        }
