from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from fare_reshop_agent.reshopping.domain.evaluation import ApprovalFlag, OfferEvaluation
from fare_reshop_agent.reshopping.domain.exchange_rate import RateUsage
from fare_reshop_agent.reshopping.domain.money import Money
from fare_reshop_agent.reshopping.domain.terms import BookingTerms
from fare_reshop_agent.reshopping.domain.trip import BookingRef, OfferId


class Status(StrEnum):
    REBOOK = "REBOOK"
    KEEP = "KEEP"
    INVALID_DATA = "INVALID_DATA"


class DecidedBy(StrEnum):
    RULES = "rules"


@dataclass(frozen=True, slots=True, kw_only=True)
class Rebook:
    status: ClassVar[Status] = Status.REBOOK
    ref: BookingRef
    offer_id: OfferId
    nominal_saving: Money
    approval_flags: tuple[ApprovalFlag, ...]
    reasoning: str
    minimum_saving: Money
    rates: tuple[RateUsage, ...]
    evaluations: tuple[OfferEvaluation, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Keep:
    status: ClassVar[Status] = Status.KEEP
    ref: BookingRef
    reasoning: str
    minimum_saving: Money
    rates: tuple[RateUsage, ...]
    evaluations: tuple[OfferEvaluation, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Invalid:
    status: ClassVar[Status] = Status.INVALID_DATA
    ref: BookingRef
    reason: str


type Recommendation = Rebook | Keep | Invalid


def decide(terms: BookingTerms, evaluations: Sequence[OfferEvaluation]) -> Rebook | Keep:
    ordered = tuple(sorted(evaluations, key=lambda evaluation: evaluation.offer_id))
    minimum = terms.minimum.money
    passing = _by_highest_saving(e for e in ordered if not e.failed_rules)
    eligible = [(e, saving) for e, saving in passing if saving >= minimum]
    if eligible:
        chosen, saving = eligible[0]
        return Rebook(
            ref=terms.booking.ref,
            offer_id=chosen.offer_id,
            nominal_saving=saving,
            approval_flags=chosen.approval_flags,
            reasoning=(
                f"Rebook to {chosen.offer_id}. It passes all seven rules and saves {saving},"
                f" which meets the minimum of {minimum}."
            ),
            minimum_saving=minimum,
            rates=terms.rates,
            evaluations=ordered,
        )
    return Keep(
        ref=terms.booking.ref,
        reasoning=_keep_reasoning(ordered, passing, minimum),
        minimum_saving=minimum,
        rates=terms.rates,
        evaluations=ordered,
    )


def _by_highest_saving(
    evaluations: Iterable[OfferEvaluation],
) -> list[tuple[OfferEvaluation, Money]]:
    with_saving = [
        (evaluation, evaluation.nominal_saving)
        for evaluation in evaluations
        if isinstance(evaluation.nominal_saving, Money)
    ]
    return sorted(with_saving, key=lambda pair: (-pair[1].amount, pair[0].offer_id))


def _keep_reasoning(
    evaluations: Sequence[OfferEvaluation],
    passing: Sequence[tuple[OfferEvaluation, Money]],
    minimum: Money,
) -> str:
    if not evaluations:
        return "No offers on this route and date."
    if passing:
        best, saving = passing[0]
        return (
            f"No offer reaches the minimum. {best.offer_id} passes all seven rules,"
            f" but its saving of {saving} is below the minimum of {minimum}."
        )
    clauses = " ".join(f"{e.offer_id} fails: {', '.join(e.failed_rules)}." for e in evaluations)
    return f"No offer passes every rule. {clauses}"
