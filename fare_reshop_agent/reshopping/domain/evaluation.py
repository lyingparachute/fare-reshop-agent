from dataclasses import dataclass
from enum import StrEnum

from fare_reshop_agent.reshopping.domain.exchange_rate import (
    Conversion,
    NoRate,
    RateUsage,
    RateUse,
)
from fare_reshop_agent.reshopping.domain.money import Money
from fare_reshop_agent.reshopping.domain.port.exchange_rates import ExchangeRates, convert
from fare_reshop_agent.reshopping.domain.terms import BookingTerms
from fare_reshop_agent.reshopping.domain.trip import Booking, Offer, OfferId


class RuleName(StrEnum):
    CABIN = "cabin"
    REFUNDABLE = "refundable"
    BAGS = "bags"
    STOPS = "stops"
    SEATS = "seats"
    FUTURE_CHANGE_FEE = "future_change_fee"
    EXCHANGE_RATE = "exchange_rate"


class RuleOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class ApprovalFlag(StrEnum):
    CARRIER_CHANGE = "carrier_change"
    SCHEDULE_CHANGE = "schedule_change"


@dataclass(frozen=True, slots=True, kw_only=True)
class RuleResult:
    rule: RuleName
    outcome: RuleOutcome
    reason: str

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError(f"rule {self.rule} needs a reason")


@dataclass(frozen=True, slots=True, kw_only=True)
class OfferEvaluation:
    offer_id: OfferId
    rules: tuple[RuleResult, ...]
    nominal_saving: Money | NoRate
    rates: tuple[RateUsage, ...]
    approval_flags: tuple[ApprovalFlag, ...]

    def __post_init__(self) -> None:
        if tuple(result.rule for result in self.rules) != tuple(RuleName):
            raise ValueError(f"evaluation of {self.offer_id} must hold every rule in order")

    @property
    def failed_rules(self) -> tuple[RuleName, ...]:
        return tuple(r.rule for r in self.rules if r.outcome is RuleOutcome.FAIL)


def evaluate_offer(terms: BookingTerms, offer: Offer, rates: ExchangeRates) -> OfferEvaluation:
    booking = terms.booking
    currency = booking.price_per_passenger.currency
    price = convert(offer.price, currency, rates)
    offer_fee = convert(offer.change_fee_per_passenger, currency, rates)
    return OfferEvaluation(
        offer_id=offer.offer_id,
        rules=(
            _cabin_rule(booking, offer),
            _refundable_rule(booking, offer),
            _bags_rule(booking, offer),
            _stops_rule(booking, offer),
            _seats_rule(booking, offer),
            _future_change_fee_rule(price, offer_fee, terms.change_fee),
            _exchange_rate_rule(price, offer_fee),
        ),
        nominal_saving=_nominal_saving(terms, price),
        rates=_usages(price, RateUse.OFFER_PRICE) + _usages(offer_fee, RateUse.OFFER_CHANGE_FEE),
        approval_flags=_approval_flags(booking, offer),
    )


def _nominal_saving(terms: BookingTerms, price: Conversion | NoRate) -> Money | NoRate:
    match price:
        case Conversion():
            booking = terms.booking
            per_passenger = booking.price_per_passenger - price.money - terms.change_fee.money
            return per_passenger.times(booking.passengers).rounded()
        case NoRate():
            return price


def _usages(conversion: Conversion | NoRate, use: RateUse) -> tuple[RateUsage, ...]:
    match conversion:
        case Conversion():
            return conversion.usages(use)
        case NoRate():
            return ()


def _rule(rule: RuleName, *, failed: bool, fail_reason: str, pass_reason: str) -> RuleResult:
    if failed:
        return RuleResult(rule=rule, outcome=RuleOutcome.FAIL, reason=fail_reason)
    return RuleResult(rule=rule, outcome=RuleOutcome.PASS, reason=pass_reason)


def _cabin_rule(booking: Booking, offer: Offer) -> RuleResult:
    return _rule(
        RuleName.CABIN,
        failed=offer.cabin.rank < booking.cabin.rank,
        fail_reason=f"offer cabin {offer.cabin} is below the booked cabin {booking.cabin}",
        pass_reason=f"offer cabin {offer.cabin} is not below the booked cabin {booking.cabin}",
    )


def _refundable_rule(booking: Booking, offer: Offer) -> RuleResult:
    return _rule(
        RuleName.REFUNDABLE,
        failed=booking.refundable and not offer.refundable,
        fail_reason="the booking is refundable and the offer is not",
        pass_reason="the offer keeps the booking's refund right",
    )


def _bags_rule(booking: Booking, offer: Offer) -> RuleResult:
    counts = f"offer includes {offer.checked_bags}, booking includes {booking.checked_bags}"
    return _rule(
        RuleName.BAGS,
        failed=offer.checked_bags < booking.checked_bags,
        fail_reason=f"fewer checked bags: {counts}",
        pass_reason=f"no fewer checked bags: {counts}",
    )


def _stops_rule(booking: Booking, offer: Offer) -> RuleResult:
    counts = f"offer has {offer.stops}, booking has {booking.stops}"
    return _rule(
        RuleName.STOPS,
        failed=offer.stops > booking.stops,
        fail_reason=f"more stops: {counts}",
        pass_reason=f"no more stops: {counts}",
    )


def _seats_rule(booking: Booking, offer: Offer) -> RuleResult:
    counts = f"{offer.seats_available} seats available, {booking.passengers} needed"
    return _rule(
        RuleName.SEATS,
        failed=offer.seats_available < booking.passengers,
        fail_reason=f"too few seats: {counts}",
        pass_reason=f"enough seats: {counts}",
    )


def _future_change_fee_rule(
    price: Conversion | NoRate, offer_fee: Conversion | NoRate, booking_fee: Conversion
) -> RuleResult:
    match price, offer_fee:
        case NoRate(), _:
            return _missing_rate(RuleName.FUTURE_CHANGE_FEE, price, "the offer's price")
        case _, NoRate():
            return _missing_rate(RuleName.FUTURE_CHANGE_FEE, offer_fee, "the offer's change fee")
        case _, Conversion():
            fees = f"offer {offer_fee.money.rounded()}, booking {booking_fee.money.rounded()}"
            return _rule(
                RuleName.FUTURE_CHANGE_FEE,
                failed=offer_fee.money > booking_fee.money,
                fail_reason=f"higher future change fee: {fees}",
                pass_reason=f"no higher future change fee: {fees}",
            )


def _exchange_rate_rule(price: Conversion | NoRate, offer_fee: Conversion | NoRate) -> RuleResult:
    missing = tuple(
        conversion.reason for conversion in (price, offer_fee) if isinstance(conversion, NoRate)
    )
    return _rule(
        RuleName.EXCHANGE_RATE,
        failed=bool(missing),
        fail_reason="; ".join(dict.fromkeys(missing)),
        pass_reason="every amount is in the booking's currency or has a rate",
    )


def _missing_rate(rule: RuleName, missing: NoRate, amount: str) -> RuleResult:
    return RuleResult(rule=rule, outcome=RuleOutcome.FAIL, reason=f"{missing.reason} for {amount}")


def _approval_flags(booking: Booking, offer: Offer) -> tuple[ApprovalFlag, ...]:
    flags: list[ApprovalFlag] = []
    if offer.carrier != booking.carrier:
        flags.append(ApprovalFlag.CARRIER_CHANGE)
    if offer.departure != booking.departure or offer.arrival != booking.arrival:
        flags.append(ApprovalFlag.SCHEDULE_CHANGE)
    return tuple(sorted(flags))
