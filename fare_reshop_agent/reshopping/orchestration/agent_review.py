from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar, assert_never

from fare_reshop_agent.reshopping.domain.evaluation import (
    ApprovalFlag,
    RuleOutcome,
    evaluate_offer,
)
from fare_reshop_agent.reshopping.domain.money import Money
from fare_reshop_agent.reshopping.domain.recommendation import Rebook, Recommendation, Status
from fare_reshop_agent.reshopping.domain.trip import BookingRef, OfferId
from fare_reshop_agent.reshopping.orchestration.booking_loop import (
    Answered,
    IncompleteReason,
    LoopRun,
    Stopped,
)
from fare_reshop_agent.reshopping.orchestration.booking_tools import BookingTools
from fare_reshop_agent.reshopping.orchestration.final_answer import (
    FinalAnswer,
    KeepAnswer,
    RebookAnswer,
)

MODEL_TEXT = "Model text: "
DISAGREEMENT = "Model and rules disagree."
INCOMPLETE_REASONING = {
    IncompleteReason.TURN_CAP: "The model gave no final answer within the turn limit.",
    IncompleteReason.REPEATED_CALL: "The model repeated the same tool call twice in a row.",
    IncompleteReason.BAD_FINAL_ANSWER: "The model's final answer did not have the required shape.",
    IncompleteReason.REFUSAL: "The model refused to answer.",
    IncompleteReason.PROVIDER_ERROR: "The model provider failed before an answer.",
}
PERSON_REVIEWS = " A person must review this booking."


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelRebook:
    status: ClassVar[Status] = Status.REBOOK
    rules: Rebook
    offer_id: OfferId
    nominal_saving: Money
    approval_flags: tuple[ApprovalFlag, ...]
    best_offer_id: OfferId | None
    confidence: Decimal
    reasoning: str

    @property
    def ref(self) -> BookingRef:
        return self.rules.ref


@dataclass(frozen=True, slots=True, kw_only=True)
class NeedsReview:
    status: ClassVar[Status] = Status.NEEDS_REVIEW
    rules: Rebook
    offer_id: OfferId | None
    nominal_saving: Money | None
    approval_flags: tuple[ApprovalFlag, ...]
    confidence: Decimal
    reasoning: str

    @property
    def ref(self) -> BookingRef:
        return self.rules.ref


@dataclass(frozen=True, slots=True, kw_only=True)
class Incomplete:
    status: ClassVar[Status] = Status.INCOMPLETE_ANALYSIS
    rules: Rebook
    reason: IncompleteReason

    @property
    def ref(self) -> BookingRef:
        return self.rules.ref

    @property
    def reasoning(self) -> str:
        return INCOMPLETE_REASONING[self.reason] + PERSON_REVIEWS


type ModelOutcome = ModelRebook | NeedsReview | Incomplete
type AgentOutcome = Recommendation | ModelOutcome


def judge(rules: Rebook, run: LoopRun, tools: BookingTools) -> ModelOutcome:
    end = run.end
    match end:
        case Stopped():
            return Incomplete(rules=rules, reason=end.reason)
        case Answered():
            return _check_answer(rules, end.answer, tools)
        case _:
            assert_never(end)


def _check_answer(rules: Rebook, answer: FinalAnswer, tools: BookingTools) -> ModelOutcome:
    match answer:
        case KeepAnswer():
            return NeedsReview(
                rules=rules,
                offer_id=None,
                nominal_saving=None,
                approval_flags=(),
                confidence=answer.confidence,
                reasoning=f"{DISAGREEMENT} {_rules_view(rules)} {MODEL_TEXT}{answer.reasoning}",
            )
        case RebookAnswer():
            return _check_rebook(rules, answer, tools)
        case _:
            assert_never(answer)


def _check_rebook(rules: Rebook, answer: RebookAnswer, tools: BookingTools) -> ModelOutcome:
    offer = next((o for o in tools.offers if o.offer_id == answer.offer_id), None)
    if offer is None:
        return _failed_choice(
            rules, answer, f"offer {answer.offer_id} is not on this route and date", None, ()
        )
    evaluation = evaluate_offer(tools.terms, offer, tools.rates)
    saving = evaluation.nominal_saving
    failed = [r for r in evaluation.rules if r.outcome is RuleOutcome.FAIL]
    match saving:
        case Money() if evaluation.is_eligible(rules.minimum_saving):
            return ModelRebook(
                rules=rules,
                offer_id=answer.offer_id,
                nominal_saving=saving,
                approval_flags=evaluation.approval_flags,
                best_offer_id=None if answer.offer_id == rules.offer_id else rules.offer_id,
                confidence=answer.confidence,
                reasoning=f"{MODEL_TEXT}{answer.reasoning}",
            )
        case Money() if not failed:
            check = "nominal saving is below the minimum saving"
        case _:
            check = f"rule {failed[0].rule} failed, {failed[0].reason}"
    shown = saving if isinstance(saving, Money) else None
    return _failed_choice(rules, answer, check, shown, evaluation.approval_flags)


def _failed_choice(
    rules: Rebook,
    answer: RebookAnswer,
    check: str,
    saving: Money | None,
    flags: tuple[ApprovalFlag, ...],
) -> NeedsReview:
    return NeedsReview(
        rules=rules,
        offer_id=answer.offer_id,
        nominal_saving=saving,
        approval_flags=flags,
        confidence=answer.confidence,
        reasoning=f"Safety check: {check}. {_rules_view(rules)} {MODEL_TEXT}{answer.reasoning}",
    )


def _rules_view(rules: Rebook) -> str:
    return (
        f"Rules view: {rules.offer_id} passes every rule and saves {rules.nominal_saving},"
        f" which meets the minimum of {rules.minimum_saving}."
    )
