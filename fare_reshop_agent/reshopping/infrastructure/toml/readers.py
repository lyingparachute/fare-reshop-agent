import tomllib
from collections.abc import Sequence
from pathlib import Path

from pydantic import Field, StrictStr

from fare_reshop_agent.reshopping.domain.exchange_rate import ExchangeRate, NoRate
from fare_reshop_agent.reshopping.domain.money import Currency, Money, decimal_from_text
from fare_reshop_agent.reshopping.domain.terms import ReviewPolicy
from fare_reshop_agent.reshopping.infrastructure.file_problem import (
    FileProblem,
    FileReadError,
    StrictRecord,
    exact_date,
    read_model,
)


class TomlFileError(FileReadError):
    pass


class _RateEntry(StrictRecord):
    base: StrictStr
    quote: StrictStr
    rate: StrictStr
    as_of: StrictStr


class _RatesFile(StrictRecord):
    comment: StrictStr | None = Field(default=None, alias="_comment")
    rates: tuple[_RateEntry, ...]


class _MinimumSaving(StrictRecord):
    amount: StrictStr
    currency: StrictStr


class _PolicyFile(StrictRecord):
    comment: StrictStr | None = Field(default=None, alias="_comment")
    minimum_saving: _MinimumSaving


class TomlExchangeRates:
    def __init__(self, rates: Sequence[ExchangeRate]) -> None:
        self._rates = tuple(rates)

    def find_rate(self, source: Currency, target: Currency) -> ExchangeRate | NoRate:
        for rate in self._rates:
            if {rate.base, rate.quote} == {source, target}:
                return rate
        return NoRate(source=source, target=target)


def read_exchange_rates(path: Path) -> TomlExchangeRates:
    parsed = read_model(path, _RatesFile, TomlFileError, tomllib.loads, tomllib.TOMLDecodeError)
    try:
        rates = tuple(
            ExchangeRate(
                base=Currency(code=entry.base),
                quote=Currency(code=entry.quote),
                rate=decimal_from_text(entry.rate, "rate"),
                as_of=exact_date(entry.as_of),
            )
            for entry in parsed.rates
        )
    except ValueError as err:
        raise TomlFileError(path=path, problem=FileProblem.MALFORMED, fact=str(err)) from err
    pairs = [frozenset((rate.base, rate.quote)) for rate in rates]
    if len(set(pairs)) != len(pairs):
        raise TomlFileError(
            path=path, problem=FileProblem.MALFORMED, fact="a currency pair is listed twice"
        )
    return TomlExchangeRates(rates)


def read_policy(path: Path) -> ReviewPolicy:
    parsed = read_model(path, _PolicyFile, TomlFileError, tomllib.loads, tomllib.TOMLDecodeError)
    try:
        return ReviewPolicy(
            minimum_saving=Money.of(
                parsed.minimum_saving.amount, Currency(code=parsed.minimum_saving.currency)
            )
        )
    except ValueError as err:
        raise TomlFileError(path=path, problem=FileProblem.MALFORMED, fact=str(err)) from err
