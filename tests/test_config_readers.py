import shutil
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pytest

from fare_reshop_agent.reshopping.domain.exchange_rate import ExchangeRate, NoRate
from fare_reshop_agent.reshopping.infrastructure.file_problem import FileProblem
from fare_reshop_agent.reshopping.infrastructure.toml.readers import (
    TomlFileError,
    read_exchange_rates,
    read_policy,
)

from sample_data import EUR, EUR_USD, GBP, POLICY, REPO_CONFIG, USD


def copied_config(tmp_path: Path) -> Path:
    folder = tmp_path / "config"
    shutil.copytree(REPO_CONFIG, folder)
    return folder


def replace_text(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_rate_file_rate_is_read_as_exact_text(tmp_path: Path) -> None:
    path = copied_config(tmp_path) / "exchange_rates.toml"
    replace_text(path, 'rate = "1.1433"', 'rate = "1.14330000000001"')

    rate = read_exchange_rates(path).find_rate(USD, EUR)

    assert isinstance(rate, ExchangeRate)
    assert rate.rate == Decimal("1.14330000000001")
    assert rate.direction == "1 EUR = 1.14330000000001 USD"


def test_missing_pair_returns_no_rate() -> None:
    rates = read_exchange_rates(REPO_CONFIG / "exchange_rates.toml")

    assert rates.find_rate(GBP, USD) == NoRate(source=GBP, target=USD)


def test_bad_policy_file_raises_toml_file_error(tmp_path: Path) -> None:
    path = copied_config(tmp_path) / "policy.toml"
    replace_text(path, 'amount = "50.00"', 'amount = "fifty"')

    with pytest.raises(TomlFileError) as raised:
        read_policy(path)

    assert raised.value.problem is FileProblem.MALFORMED
    assert raised.value.fact


def test_repo_config_holds_the_demo_rate_and_minimum() -> None:
    rate = read_exchange_rates(REPO_CONFIG / "exchange_rates.toml").find_rate(EUR, USD)

    assert rate == EUR_USD
    assert read_policy(REPO_CONFIG / "policy.toml") == POLICY


@pytest.mark.parametrize(
    ("reader", "file_name", "old", "new"),
    [
        (read_exchange_rates, "exchange_rates.toml", 'rate = "1.1433"', "rate = 1.1433"),
        (read_exchange_rates, "exchange_rates.toml", 'as_of = "2026-07-07"', 'as_of = "2026-7-7"'),
        (read_exchange_rates, "exchange_rates.toml", 'quote = "USD"', 'quote = "USD"\nnote = "x"'),
        (read_exchange_rates, "exchange_rates.toml", "[[rates]]", "[[rates]"),
        (
            read_exchange_rates,
            "exchange_rates.toml",
            'as_of = "2026-07-07"',
            'as_of = "2026-07-07"\n\n[[rates]]\nbase = "USD"\nquote = "EUR"\n'
            'rate = "0.87"\nas_of = "2026-07-07"',
        ),
        (read_policy, "policy.toml", 'currency = "USD"', 'currency = "usd"'),
        (read_policy, "policy.toml", 'currency = "USD"', 'currency = "USD"\nnote = "x"'),
        (read_policy, "policy.toml", 'amount = "50.00"', 'amount = "-50.00"'),
    ],
)
def test_bad_config_file_raises_toml_file_error(
    tmp_path: Path, reader: Callable[[Path], object], file_name: str, old: str, new: str
) -> None:
    path = copied_config(tmp_path) / file_name
    replace_text(path, old, new)

    with pytest.raises(TomlFileError) as raised:
        reader(path)

    assert raised.value.problem is FileProblem.MALFORMED


def test_missing_config_file_raises_toml_file_error(tmp_path: Path) -> None:
    with pytest.raises(TomlFileError) as raised:
        read_policy(tmp_path / "policy.toml")

    assert raised.value.problem is FileProblem.MISSING
