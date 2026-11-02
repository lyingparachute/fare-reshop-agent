import json
from typing import assert_never

from fare_reshop_agent.reshopping.domain.evaluation import OfferEvaluation
from fare_reshop_agent.reshopping.domain.exchange_rate import NoRate, RateUsage
from fare_reshop_agent.reshopping.domain.money import Money
from fare_reshop_agent.reshopping.domain.port.reshop_source import DataIssue
from fare_reshop_agent.reshopping.domain.recommendation import (
    DecidedBy,
    Invalid,
    Keep,
    Rebook,
    Recommendation,
    Status,
)
from fare_reshop_agent.reshopping.orchestration.review import ReviewReport

SCHEMA_VERSION = 1
AS_OF_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
JSON_INDENT = 2

type Json = bool | int | str | list[Json] | dict[str, Json] | None


def render_json(report: ReviewReport) -> str:
    document: dict[str, Json] = {
        "schema_version": SCHEMA_VERSION,
        "mode": report.mode.value,
        "as_of": report.as_of.strftime(AS_OF_FORMAT),
        "data_issues": [_data_issue(issue) for issue in report.data_issues],
        "results": [_result(result) for result in report.results],
    }
    return json.dumps(document, indent=JSON_INDENT)


def _data_issue(issue: DataIssue) -> dict[str, Json]:
    return {"kind": issue.kind.value, "id": issue.record_id, "reason": issue.reason}


def _result(result: Recommendation) -> dict[str, Json]:
    match result:
        case Rebook():
            choice: dict[str, Json] = {
                "offer_id": result.offer_id,
                "nominal_saving": _money(result.nominal_saving),
                "approval_flags": [flag.value for flag in result.approval_flags],
            }
            return _row(result, choice, _judgement(result))
        case Keep():
            return _row(result, _no_choice(), _judgement(result))
        case Invalid():
            judgement: dict[str, Json] = {
                "reasoning": None,
                "minimum_saving": None,
                "exchange_rates": [],
                "invalid_reason": result.reason,
                "evaluations": [],
            }
            return _row(result, _no_choice(), judgement)
        case _:
            assert_never(result)


def _no_choice() -> dict[str, Json]:
    return {"offer_id": None, "nominal_saving": None, "approval_flags": []}


def _judgement(result: Rebook | Keep) -> dict[str, Json]:
    return {
        "reasoning": result.reasoning,
        "minimum_saving": _money(result.minimum_saving),
        "exchange_rates": [_rate(usage) for usage in result.rates],
        "invalid_reason": None,
        "evaluations": [_evaluation(evaluation) for evaluation in result.evaluations],
    }


def _row(
    result: Recommendation, choice: dict[str, Json], judgement: dict[str, Json]
) -> dict[str, Json]:
    header: dict[str, Json] = {
        "pnr": result.ref,
        "status": result.status.value,
        "rebook": result.status is Status.REBOOK,
        "decided_by": DecidedBy.RULES.value,
        "incomplete_reason": None,
    }
    return header | choice | {"confidence": None} | judgement


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


def _rate(usage: RateUsage) -> dict[str, Json]:
    return {
        "use": usage.use.value,
        "rate": str(usage.rate.rate),
        "direction": usage.rate.direction,
        "as_of": usage.rate.as_of.isoformat(),
    }
