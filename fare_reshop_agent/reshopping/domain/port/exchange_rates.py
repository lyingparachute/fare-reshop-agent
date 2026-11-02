from typing import Protocol

from fare_reshop_agent.reshopping.domain.exchange_rate import Conversion, ExchangeRate, NoRate
from fare_reshop_agent.reshopping.domain.money import Currency, Money


class ExchangeRates(Protocol):
    def find_rate(self, source: Currency, target: Currency) -> ExchangeRate | NoRate: ...


def convert(money: Money, target: Currency, rates: ExchangeRates) -> Conversion | NoRate:
    if money.currency == target:
        return Conversion(money=money, rates=())
    rate = rates.find_rate(money.currency, target)
    match rate:
        case ExchangeRate():
            return Conversion(money=rate.convert(money), rates=(rate,))
        case NoRate():
            return rate
