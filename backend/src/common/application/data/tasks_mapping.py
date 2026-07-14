from src.common.application.commands.common import SendEmailCommand
from src.common.application.commands.tenants import SoftDeleteTenantCommand
from src.common.application.commands.users import MergeTenantsCommand
from src.common.domain.buses.commands import Command

async_tasks_mapping: dict[str, type[Command]] = {
    SendEmailCommand.__name__: SendEmailCommand,
    MergeTenantsCommand.__name__: MergeTenantsCommand,
    SoftDeleteTenantCommand.__name__: SoftDeleteTenantCommand,
}
