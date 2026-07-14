from abc import ABC, abstractmethod
from typing import Any


class EmailService(ABC):
    @abstractmethod
    async def send_email(
        self,
        subject: str | None,
        sender: str | None,
        recipients: list[str],
        template_name: str,
        context: dict[str, Any],
    ) -> None:
        raise NotImplementedError
