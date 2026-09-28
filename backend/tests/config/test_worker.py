from unittest.mock import create_autospec

from expects import equal, expect
from redis.asyncio import Redis

from config.worker import CommandRunner
from src.common.database.config import DatabaseConfig
from src.common.domain.buses.async_commands import CommandEnqueuer


async def test_command_runner__reports_an_unregistered_command_as_a_permanent_failure(
    database_config: DatabaseConfig,
):
    runner = CommandRunner(
        database_config=database_config,
        redis_client=create_autospec(spec=Redis, instance=True),
        enqueuer=create_autospec(spec=CommandEnqueuer, spec_set=True, instance=True),
    )

    result = await runner({"command_name": "UnknownCommand", "payload": {}})

    expect(result.is_success).to(equal(False))
    expect(result.reason).to(equal("NotRegisteredCommand"))
