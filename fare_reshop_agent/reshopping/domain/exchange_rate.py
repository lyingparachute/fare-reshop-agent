from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from fare_reshop_agent.reshopping.domain.money import Currency, Money


@dataclass(frozen=True, slots=True, kw_only=True)
class ExchangeRate:
    base: Currency
    quote: Currency
    rate: Decimal
    as_of: date

    def __post_init__(self) -> None:
        if self.base == self.quote:
            raise ValueError(f"an exchange rate needs two currencies, got {self.base} twice")
        if not isinstance(self.rate, Decimal) or not self.rate.is_finite() or self.rate <= 0:
            raise ValueError(f"an exchange rate must be a positive Decimal, got {self.rate!r}")

    @property
    def direction(self) -> str:
        return f"1 {self.base} = {self.rate} {self.quote}"

    def convert(self, money: Money) -> Money:
        if money.currency == self.base:
            return Money(amount=money.amount * self.rate, currency=self.quote)
        if money.currency == self.quote:
            return Money(amount=money.amount / self.rate, currency=self.base)
        raise ValueError(f"the {self.direction} rate cannot convert {money.currency}")


@dataclass(frozen=True, slots=True, kw_only=True)
class NoRate:
    source: Currency
    target: Currency

    @property
    def reason(self) -> str:
        return f"no exchange rate from {self.source} to {self.target}"


class RateUse(StrEnum):
    OFFER_PRICE = "offer_price"
    OFFER_CHANGE_FEE = "offer_change_fee"
    MINIMUM_SAVING = "minimum_saving"
    BOOKING_FEE = "booking_fee"


@dataclass(frozen=True, slots=True, kw_only=True)
class RateUsage:
    use: RateUse
    rate: ExchangeRate


@dataclass(frozen=True, slots=True, kw_only=True)
class Conversion:
    money: Money
    rates: tuple[ExchangeRate, ...]

    def usages(self, use: RateUse) -> tuple[RateUsage, ...]:
        return tuple(RateUsage(use=use, rate=rate) for rate in self.rates)
