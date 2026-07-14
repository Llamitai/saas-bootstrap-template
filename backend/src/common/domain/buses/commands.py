from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Self


class Command(ABC):
    @property
    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_dict(cls, kwargs: dict[str, Any]) -> Self:
        raise NotImplementedError


@dataclass
class CommandHandler[TCommand: Command](ABC):
    @abstractmethod
    async def execute(self, command: TCommand):
        raise NotImplementedError


@dataclass
class CommandBus(ABC):
    @abstractmethod
    def subscribe[TCommand: Command](self, command: type[TCommand], handler: CommandHandler[TCommand]):
        raise NotImplementedError

    @abstractmethod
    async def dispatch(
        self,
        command: Command,
        run_async: bool = False,
    ):
        raise NotImplementedError
