from dataclasses import dataclass
from typing import Any

from src.common.application.logging import get_logger
from src.common.domain.buses.async_commands import CommandEnqueuer
from src.common.domain.buses.commands import Command, CommandBus, CommandHandler
from src.common.infrastructure.buses._exceptions import (
    CommandAlreadyExistError,
    CommandHandlerDoesNotExistError,
)

logger = get_logger(__name__)


@dataclass
class MemoryCommandBus(CommandBus):
    enqueuer: CommandEnqueuer

    def __post_init__(self):
        self._commands: dict[type[Command], CommandHandler[Any]] = {}

    def subscribe[TCommand: Command](self, command: type[TCommand], handler: CommandHandler[TCommand]):
        if command in self._commands:
            raise CommandAlreadyExistError
        self._commands[command] = handler

    async def dispatch(
        self,
        command: Command,
        run_async: bool = False,
    ):
        if command.__class__ not in self._commands:
            raise CommandHandlerDoesNotExistError(command.__class__)

        if run_async:
            logger.info(
                "command_bus.async_dispatch",
                command=command.__class__.__name__,
            )
            await self.enqueuer.enqueue(command)
            return
        await self._commands[command.__class__].execute(command)
