from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fare_reshop_agent.reshopping.domain.evaluation import evaluate_offer
from fare_reshop_agent.reshopping.domain.exchange_rate import NoRate
from fare_reshop_agent.reshopping.domain.port.exchange_rates import ExchangeRates
from fare_reshop_agent.reshopping.domain.port.reshop_source import (
    DataIssue,
    RejectedBooking,
    ReshopSource,
)
from fare_reshop_agent.reshopping.domain.recommendation import Invalid, Recommendation, decide
from fare_reshop_agent.reshopping.domain.terms import ReviewPolicy, booking_terms
from fare_reshop_agent.reshopping.domain.trip import Booking, Offer

DEPARTS_BEFORE_CAPTURE = "departs before the capture time"


class ReviewMode(StrEnum):
    NONE = "none"


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewReport:
    mode: ReviewMode
    as_of: datetime
    data_issues: tuple[DataIssue, ...]
    results: tuple[Recommendation, ...]


def review_snapshot(
    source: ReshopSource, rates: ExchangeRates, policy: ReviewPolicy
) -> ReviewReport:
    snapshot = source.read_snapshot()
    results = (
        _review_booking(booking, snapshot.offers, snapshot.captured_at, rates, policy)
        for booking in snapshot.bookings
    )
    return ReviewReport(
        mode=ReviewMode.NONE,
        as_of=snapshot.captured_at,
        data_issues=snapshot.data_issues,
        results=tuple(sorted(results, key=lambda result: result.ref)),
    )


def _review_booking(
    booking: Booking | RejectedBooking,
    offers: Sequence[Offer],
    captured_at: datetime,
    rates: ExchangeRates,
    policy: ReviewPolicy,
) -> Recommendation:
    if isinstance(booking, RejectedBooking):
        return Invalid(ref=booking.ref, reason=booking.reason)
    if booking.departure < captured_at.replace(tzinfo=None):
        return Invalid(ref=booking.ref, reason=DEPARTS_BEFORE_CAPTURE)
    terms = booking_terms(booking, policy, rates)
    if isinstance(terms, NoRate):
        return Invalid(ref=booking.ref, reason=terms.reason)
    on_route = [offer for offer in offers if offer.route == booking.route]
    return decide(terms, [evaluate_offer(terms, offer, rates) for offer in on_route])
