from dataclasses import dataclass

from fare_reshop_agent.reshopping.domain.exchange_rate import (
    Conversion,
    NoRate,
    RateUsage,
    RateUse,
)
from fare_reshop_agent.reshopping.domain.money import Currency, Money
from fare_reshop_agent.reshopping.domain.port.exchange_rates import ExchangeRates, convert
from fare_reshop_agent.reshopping.domain.trip import Booking


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewPolicy:
    minimum_saving: Money

    def __post_init__(self) -> None:
        if self.minimum_saving.is_negative():
            raise ValueError(f"the minimum saving must not be negative, got {self.minimum_saving}")


@dataclass(frozen=True, slots=True, kw_only=True)
class BookingTerms:
    booking: Booking
    change_fee: Conversion
    minimum: Conversion

    @property
    def rates(self) -> tuple[RateUsage, ...]:
        return self.change_fee.usages(RateUse.BOOKING_FEE) + self.minimum.usages(
            RateUse.MINIMUM_SAVING
        )


def convert_minimum(
    policy: ReviewPolicy, currency: Currency, rates: ExchangeRates
) -> Conversion | NoRate:
    conversion = convert(policy.minimum_saving, currency, rates)
    match conversion:
        case Conversion():
            return Conversion(money=conversion.money.rounded(), rates=conversion.rates)
        case NoRate():
            return conversion


def booking_terms(
    booking: Booking, policy: ReviewPolicy, rates: ExchangeRates
) -> BookingTerms | NoRate:
    currency = booking.price_per_passenger.currency
    change_fee = convert(booking.change_fee_per_passenger, currency, rates)
    if isinstance(change_fee, NoRate):
        return change_fee
    minimum = convert_minimum(policy, currency, rates)
    if isinstance(minimum, NoRate):
        return minimum
    return BookingTerms(booking=booking, change_fee=change_fee, minimum=minimum)
