from dataclasses import dataclass
from typing import Any

from src.common.domain.interfaces.presenter import Presenter
from src.common.domain.models.user import User
from src.common.presentation.presenters.email_address import EmailAddressPresenter


@dataclass
class RegisteredUserPresenter(Presenter[User]):
    """Public view of a just-registered account: no role, tenant or privilege data."""

    instance: User

    @property
    def to_dict(self) -> dict[str, Any]:
        return {
            "uuid": str(self.instance.uuid),
            "username": self.instance.username,
            "first_name": self.instance.first_name,
            "last_name": self.instance.last_name,
            "email_address": (
                EmailAddressPresenter(self.instance.email_address).to_dict if self.instance.email_address else None
            ),
        }
