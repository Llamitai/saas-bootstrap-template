from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.infrastructure.bus_wiring import auth_wiring
from src.common.domain.buses.async_commands import CommandEnqueuer
from src.common.domain.contexts.bus import BusContext
from src.common.domain.contexts.domain import DomainContext
from src.common.infrastructure.buses import MemoryCommandBus, MemoryEventBus, MemoryQueryBus
from src.messaging.infrastructure.bus_wiring import messaging_wiring
from src.tenants.infrastructure.bus_wiring import tenants_wiring
from src.users.infrastructure.bus_wiring import users_wiring


def build_async_bus(
    session: AsyncSession,
    domain: DomainContext,
    enqueuer: CommandEnqueuer,
) -> BusContext:
    """`enqueuer` is the process-wide RabbitMQ publisher owned by the lifespan or worker."""
    bus = BusContext(
        command_bus=MemoryCommandBus(enqueuer=enqueuer),
        query_bus=MemoryQueryBus(),
        event_bus=MemoryEventBus(),
    )

    auth_wiring(domain, bus)
    messaging_wiring(domain, bus)
    tenants_wiring(domain, bus)
    users_wiring(domain, bus)
    return bus
