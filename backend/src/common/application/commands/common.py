from dataclasses import asdict, dataclass
from typing import Any

from src.common.domain.buses.commands import Command


@dataclass
class SendEmailCommand(Command):
    to_emails: list[str]
    template_name: str
    context: dict[str, Any] | None = None
    from_email: str | None = None
    subject: str | None = None

    @property
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, kwargs: dict) -> "SendEmailCommand":
        return cls(**kwargs)
