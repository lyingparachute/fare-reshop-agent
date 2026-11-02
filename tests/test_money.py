import dataclasses
import decimal
import json
from decimal import Decimal

import pytest

from fare_reshop_agent.reshopping.domain.money import Money

from sample_data import EUR, EUR_USD, QX7T2A, USD, eur, usd


def test_money_rejects_float_input() -> None:
    with pytest.raises(TypeError, match="float"):
        Money.of(json.loads("80.0"), USD)


def test_money_rejects_bool_input() -> None:
    with pytest.raises(TypeError, match="bool"):
        Money.of(True, USD)


def test_money_accepts_text_and_int() -> None:
    from_text = Money.of("80.00", USD)
    from_int = Money.of(80, USD)

    assert isinstance(from_text.amount, Decimal)
    assert isinstance(from_int.amount, Decimal)
    assert from_text == from_int


def test_adding_two_currencies_raises() -> None:
    with pytest.raises(ValueError, match="USD with EUR"):
        usd("1") + eur("1")


def test_ordering_two_currencies_raises() -> None:
    with pytest.raises(ValueError, match="USD with EUR"):
        _ = usd("1") < eur("1")


def test_equality_across_currencies_raises() -> None:
    with pytest.raises(ValueError, match="USD with EUR"):
        _ = usd("50") == eur("50")


def test_exchange_rate_converts_in_both_directions() -> None:
    assert EUR_USD.convert(usd("1.1433")) == Money(amount=Decimal("1"), currency=EUR)
    assert EUR_USD.convert(eur("1")) == Money(amount=Decimal("1.1433"), currency=USD)


def test_float_trap_rejects_decimal_from_float() -> None:
    with pytest.raises(decimal.FloatOperation):
        Decimal(json.loads("0.1"))


def test_counts_refuse_bool() -> None:
    with pytest.raises(TypeError, match="whole number"):
        dataclasses.replace(QX7T2A, passengers=True)
