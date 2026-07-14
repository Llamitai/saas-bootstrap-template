"""Mocked dependencies for users application-layer use cases.

Buses are wired here with `create_autospec` so each test overrides only
the return values it cares about, without bringing the real DB into scope.
"""

from unittest.mock import create_autospec

import pytest

from src.common.domain.buses.commands import CommandBus
from src.common.domain.buses.queries import QueryBus


@pytest.fixture
def query_bus():
    return create_autospec(spec=QueryBus, spec_set=True, instance=True)


@pytest.fixture
def command_bus():
    return create_autospec(spec=CommandBus, spec_set=True, instance=True)
