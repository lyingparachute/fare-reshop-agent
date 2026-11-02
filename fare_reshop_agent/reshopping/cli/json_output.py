import json
from decimal import Decimal
from typing import assert_never

from fare_reshop_agent.reshopping.domain.evaluation import ApprovalFlag, OfferEvaluation
from fare_reshop_agent.reshopping.domain.exchange_rate import NoRate, RateUsage
from fare_reshop_agent.reshopping.domain.money import Money
from fare_reshop_agent.reshopping.domain.port.reshop_source import DataIssue
from fare_reshop_agent.reshopping.domain.recommendation import (
    DecidedBy,
    Invalid,
    Keep,
    Rebook,
    Status,
)
from fare_reshop_agent.reshopping.domain.trip import OfferId
from fare_reshop_agent.reshopping.orchestration.agent_review import (
    AgentOutcome,
    Incomplete,
    ModelRebook,
    NeedsReview,
)
from fare_reshop_agent.reshopping.orchestration.booking_loop import Trace
from fare_reshop_agent.reshopping.orchestration.replay import RecordedTrace
from fare_reshop_agent.reshopping.orchestration.review import ReviewReport, ReviewRow

SCHEMA_VERSION = 1
AS_OF_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
JSON_INDENT = 2
CONFIDENCE_NOTE = "model estimate, not calibrated"

type Json = bool | int | str | list[Json] | dict[str, Json] | None


def render_json(report: ReviewReport) -> str:
    document: dict[str, Json] = {
        "schema_version": SCHEMA_VERSION,
        "mode": report.mode.value,
        "as_of": report.as_of.strftime(AS_OF_FORMAT),
        "data_issues": [_data_issue(issue) for issue in report.data_issues],
        "results": [_result(row) for row in report.results],
    }
    return json.dumps(document, indent=JSON_INDENT)


def _data_issue(issue: DataIssue) -> dict[str, Json]:
    return {"kind": issue.kind.value, "id": issue.record_id, "reason": issue.reason}


def _result(row: ReviewRow) -> dict[str, Json]:
    outcome = row.outcome
    header: dict[str, Json] = {
        "pnr": outcome.ref,
        "status": outcome.status.value,
        "rebook": outcome.status is Status.REBOOK,
        "decided_by": _decided_by(outcome),
        "incomplete_reason": outcome.reason.value if isinstance(outcome, Incomplete) else None,
    }
    choice = _choice(outcome)
    best: dict[str, Json] = {}
    trace: dict[str, Json] = {}
    if row.trace is not None:
        best_offer = outcome.best_offer_id if isinstance(outcome, ModelRebook) else None
        best = {"best_offer_id": best_offer}
        trace = {"trace": _trace(row.trace)}
    return header | choice | best | _confidence(outcome) | _judgement(outcome) | trace


def _decided_by(outcome: AgentOutcome) -> Json:
    match outcome:
        case Rebook() | Keep() | Invalid():
            return DecidedBy.RULES.value
        case ModelRebook():
            return DecidedBy.MODEL.value
        case NeedsReview():
            return DecidedBy.SAFETY_CHECK.value
        case Incomplete():
            return None
        case _:
            assert_never(outcome)


def _choice(outcome: AgentOutcome) -> dict[str, Json]:
    match outcome:
        case Rebook() | ModelRebook() | NeedsReview():
            return _offer_choice(outcome.offer_id, outcome.nominal_saving, outcome.approval_flags)
        case Keep() | Invalid() | Incomplete():
            return _offer_choice(None, None, ())
        case _:
            assert_never(outcome)


def _offer_choice(
    offer_id: OfferId | None, saving: Money | None, flags: tuple[ApprovalFlag, ...]
) -> dict[str, Json]:
    return {
        "offer_id": offer_id,
        "nominal_saving": None if saving is None else _money(saving),
        "approval_flags": [flag.value for flag in flags],
    }


def _confidence(outcome: AgentOutcome) -> dict[str, Json]:
    if not isinstance(outcome, ModelRebook | NeedsReview):
        return {"confidence": None}
    return {"confidence": _decimal(outcome.confidence), "confidence_note": CONFIDENCE_NOTE}


def _judgement(outcome: AgentOutcome) -> dict[str, Json]:
    match outcome:
        case Invalid():
            return {
                "reasoning": None,
                "minimum_saving": None,
                "exchange_rates": [],
                "invalid_reason": outcome.reason,
                "evaluations": [],
            }
        case Rebook() | Keep():
            return _rules_judgement(outcome.reasoning, outcome)
        case ModelRebook() | NeedsReview() | Incomplete():
            return _rules_judgement(outcome.reasoning, outcome.rules)
        case _:
            assert_never(outcome)


def _rules_judgement(reasoning: str, rules: Rebook | Keep) -> dict[str, Json]:
    return {
        "reasoning": reasoning,
        "minimum_saving": _money(rules.minimum_saving),
        "exchange_rates": [_rate(usage) for usage in rules.rates],
        "invalid_reason": None,
        "evaluations": [_evaluation(evaluation) for evaluation in rules.evaluations],
    }


def _trace(trace: Trace | RecordedTrace) -> dict[str, Json]:
    match trace:
        case Trace():
            return {
                "prompt_version": trace.prompt_version,
                "turns": trace.turns,
                "usage": _usage(trace),
                **_calls_and_error(trace),
            }
        case RecordedTrace():
            return {
                "prompt_version": trace.trace.prompt_version,
                "turns": trace.trace.turns,
                "recorded_model": trace.recorded_model,
                "recorded_usage": _usage(trace.trace),
                **_calls_and_error(trace.trace),
            }
        case _:
            assert_never(trace)


def _usage(trace: Trace) -> dict[str, Json]:
    return {
        "input_tokens": trace.usage.input_tokens,
        "output_tokens": trace.usage.output_tokens,
    }


def _calls_and_error(trace: Trace) -> dict[str, Json]:
    return {
        "tool_calls": [
            {"name": call.name, "arguments": call.arguments, "ok": call.ok}
            for call in trace.tool_calls
        ],
        "provider_error_code": (
            None if trace.provider_error_code is None else trace.provider_error_code.value
        ),
    }


def _evaluation(evaluation: OfferEvaluation) -> dict[str, Json]:
    saving = evaluation.nominal_saving
    return {
        "offer_id": evaluation.offer_id,
        "rules": [
            {"rule": r.rule.value, "result": r.outcome.value, "reason": r.reason}
            for r in evaluation.rules
        ],
        "nominal_saving": None if isinstance(saving, NoRate) else _money(saving),
        "exchange_rates": [_rate(usage) for usage in evaluation.rates],
        "approval_flags": [flag.value for flag in evaluation.approval_flags],
    }


def _money(money: Money) -> dict[str, Json]:
    return {"amount": f"{money.amount:.2f}", "currency": money.currency.code}


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _rate(usage: RateUsage) -> dict[str, Json]:
    return {
        "use": usage.use.value,
        "rate": str(usage.rate.rate),
        "direction": usage.rate.direction,
        "as_of": usage.rate.as_of.isoformat(),
    }
