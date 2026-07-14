from dataclasses import dataclass

from src.common.domain.buses.commands import Command, CommandBus, CommandHandler


@dataclass
class FakeCommandBus(CommandBus):
    def subscribe[TCommand: Command](self, command: type[TCommand], handler: CommandHandler[TCommand]):
        pass

    async def dispatch_batch(self, _commands: list[Command], _is_async: bool = False):
        pass

    async def dispatch(self, command: Command, run_async: bool = False):
        pass
