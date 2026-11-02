from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import assert_never

from fare_reshop_agent.reshopping.domain.evaluation import evaluate_offer
from fare_reshop_agent.reshopping.domain.exchange_rate import NoRate
from fare_reshop_agent.reshopping.domain.port.exchange_rates import ExchangeRates
from fare_reshop_agent.reshopping.domain.port.reshop_source import (
    DataIssue,
    RejectedBooking,
    ReshopSnapshot,
    ReshopSource,
)
from fare_reshop_agent.reshopping.domain.recommendation import (
    Invalid,
    Keep,
    Rebook,
    Recommendation,
    decide,
)
from fare_reshop_agent.reshopping.domain.terms import BookingTerms, ReviewPolicy, booking_terms
from fare_reshop_agent.reshopping.domain.trip import Booking, offers_on_route
from fare_reshop_agent.reshopping.orchestration.agent_model import AgentModel, Prompt
from fare_reshop_agent.reshopping.orchestration.agent_review import (
    AgentOutcome,
    check_shared_seats,
    judge,
)
from fare_reshop_agent.reshopping.orchestration.booking_loop import Trace, run_booking_loop
from fare_reshop_agent.reshopping.orchestration.booking_tools import BookingTools
from fare_reshop_agent.reshopping.orchestration.replay import RecordedTrace

DEPARTS_BEFORE_CAPTURE = "departs before the capture time"


class ReviewMode(StrEnum):
    NONE = "none"
    OPENAI = "openai"
    RECORDED = "recorded"


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewRow:
    outcome: AgentOutcome
    trace: Trace | RecordedTrace | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewReport:
    mode: ReviewMode
    as_of: datetime
    data_issues: tuple[DataIssue, ...]
    results: tuple[ReviewRow, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewAgent:
    model: AgentModel
    prompt: Prompt
    mode: ReviewMode


def review_snapshot(
    source: ReshopSource, rates: ExchangeRates, policy: ReviewPolicy
) -> ReviewReport:
    snapshot = source.read_snapshot()
    rows = (
        ReviewRow(
            outcome=_rules_outcome(_terms(b, snapshot, rates, policy), snapshot, rates), trace=None
        )
        for b in snapshot.bookings
    )
    return _report(ReviewMode.NONE, snapshot, rows)


def review_with_model(
    source: ReshopSource, rates: ExchangeRates, policy: ReviewPolicy, agent: ReviewAgent
) -> ReviewReport:
    snapshot = source.read_snapshot()
    rows = [
        _model_row(_terms(b, snapshot, rates, policy), snapshot, rates, agent)
        for b in snapshot.bookings
    ]
    return _report(agent.mode, snapshot, rows)


def _model_row(
    terms: BookingTerms | Invalid,
    snapshot: ReshopSnapshot,
    rates: ExchangeRates,
    agent: ReviewAgent,
) -> ReviewRow:
    if isinstance(terms, Invalid):
        return ReviewRow(outcome=terms, trace=Trace.empty(agent.prompt))
    rules = _decide(terms, snapshot, rates)
    match rules:
        case Keep():
            return ReviewRow(outcome=rules, trace=Trace.empty(agent.prompt))
        case Rebook():
            tools = BookingTools.for_booking(terms, snapshot.offers, rates)
            run = run_booking_loop(tools, agent.model, agent.prompt)
            return ReviewRow(outcome=judge(rules, run, tools), trace=run.trace)
        case _:
            assert_never(rules)


def _rules_outcome(
    terms: BookingTerms | Invalid, snapshot: ReshopSnapshot, rates: ExchangeRates
) -> Recommendation:
    return terms if isinstance(terms, Invalid) else _decide(terms, snapshot, rates)


def _decide(terms: BookingTerms, snapshot: ReshopSnapshot, rates: ExchangeRates) -> Rebook | Keep:
    on_route = offers_on_route(snapshot.offers, terms.booking)
    return decide(terms, [evaluate_offer(terms, offer, rates) for offer in on_route])


def _terms(
    booking: Booking | RejectedBooking,
    snapshot: ReshopSnapshot,
    rates: ExchangeRates,
    policy: ReviewPolicy,
) -> BookingTerms | Invalid:
    if isinstance(booking, RejectedBooking):
        return Invalid(ref=booking.ref, reason=booking.reason)
    if booking.departure < snapshot.captured_at.replace(tzinfo=None):
        return Invalid(ref=booking.ref, reason=DEPARTS_BEFORE_CAPTURE)
    terms = booking_terms(booking, policy, rates)
    if isinstance(terms, NoRate):
        return Invalid(ref=booking.ref, reason=terms.reason)
    return terms


def _report(mode: ReviewMode, snapshot: ReshopSnapshot, rows: Iterable[ReviewRow]) -> ReviewReport:
    ordered = sorted(rows, key=lambda row: row.outcome.ref)
    bookings = (b for b in snapshot.bookings if isinstance(b, Booking))
    checked = check_shared_seats([row.outcome for row in ordered], bookings, snapshot.offers)
    return ReviewReport(
        mode=mode,
        as_of=snapshot.captured_at,
        data_issues=snapshot.data_issues,
        results=tuple(
            ReviewRow(outcome=outcome, trace=row.trace)
            for row, outcome in zip(ordered, checked, strict=True)
        ),
    )
