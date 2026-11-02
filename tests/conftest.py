import decimal

import pytest


def pytest_configure(config: pytest.Config) -> None:
    decimal.getcontext().traps[decimal.FloatOperation] = True
