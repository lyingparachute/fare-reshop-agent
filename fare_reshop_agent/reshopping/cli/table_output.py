from dataclasses import dataclass
from typing import assert_never

from fare_reshop_agent.reshopping.composition.color import ColorSetting
from fare_reshop_agent.reshopping.domain.evaluation import ApprovalFlag
from fare_reshop_agent.reshopping.domain.recommendation import Invalid, Keep, Rebook, Status
from fare_reshop_agent.reshopping.orchestration.agent_review import (
    AgentOutcome,
    Incomplete,
    ModelRebook,
    NeedsReview,
    SeatConflict,
)
from fare_reshop_agent.reshopping.orchestration.review import ReviewMode, ReviewReport

EMPTY_CELL = "-"
COLUMN_GAP = "  "
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"
RULES_REBOOK_REASON = "Biggest saving that passes every rule."
MODEL_REBOOK_REASON = "Model pick, passes every rule."
RULES_ONLY_TITLE = "Mode: rules only, no model."
RECORDED_TITLE = "Mode: replay of a recorded model run. No model is called now."
LIVE_TITLE = "Mode: live model run."


@dataclass(frozen=True, slots=True, kw_only=True)
class _Row:
    ref: str
    status: str
    offer: str
    saving: str
    flags: str
    reason: str


HEADER = _Row(
    ref="PNR", status="STATUS", offer="OFFER", saving="SAVING", flags="FLAGS", reason="REASON"
)


def render_table(report: ReviewReport, color: ColorSetting) -> str:
    outcomes = [row.outcome for row in report.results]
    rows = [_row(outcome) for outcome in outcomes]
    every_row = [HEADER, *rows]
    ref_width = max(len(row.ref) for row in every_row)
    status_width = max(len(row.status) for row in every_row)
    offer_width = max(len(row.offer) for row in every_row)
    saving_width = max(len(row.saving) for row in every_row)
    flags_width = max(len(row.flags) for row in every_row)

    def line(row: _Row, status: str) -> str:
        return COLUMN_GAP.join(
            [
                row.ref.ljust(ref_width),
                status + " " * (status_width - len(row.status)),
                row.offer.ljust(offer_width),
                row.saving.ljust(saving_width),
                row.flags.ljust(flags_width),
                row.reason,
            ]
        )

    lines = [_title(report.mode), "", line(HEADER, HEADER.status)]
    lines.extend(
        line(row, _colored(outcome.status, color))
        for row, outcome in zip(rows, outcomes, strict=True)
    )
    lines.extend(
        f"data issue: {issue.kind} {issue.record_id}: {issue.reason}"
        for issue in report.data_issues
    )
    return "\n".join(lines)


def _row(outcome: AgentOutcome) -> _Row:
    flags: tuple[ApprovalFlag, ...] = ()
    match outcome:
        case Rebook():
            offer: str = outcome.offer_id
            saving, reason = str(outcome.nominal_saving), RULES_REBOOK_REASON
            flags = outcome.approval_flags
        case ModelRebook():
            offer = outcome.offer_id
            saving, reason = str(outcome.nominal_saving), _model_rebook_reason(outcome)
            flags = outcome.approval_flags
        case NeedsReview():
            offer = outcome.offer_id or EMPTY_CELL
            saving = EMPTY_CELL if outcome.nominal_saving is None else str(outcome.nominal_saving)
            reason = _first_sentence(outcome.reasoning)
            flags = outcome.approval_flags
        case SeatConflict():
            offer = outcome.proposal.offer_id
            saving, reason = (
                str(outcome.proposal.nominal_saving),
                _first_sentence(outcome.reasoning),
            )
            flags = outcome.proposal.approval_flags
        case Keep() | Incomplete():
            offer, saving, reason = EMPTY_CELL, EMPTY_CELL, _first_sentence(outcome.reasoning)
        case Invalid():
            offer, saving, reason = EMPTY_CELL, EMPTY_CELL, outcome.reason
        case _:
            assert_never(outcome)
    return _Row(
        ref=outcome.ref,
        status=outcome.status.value,
        offer=offer,
        saving=saving,
        flags=",".join(flags) or EMPTY_CELL,
        reason=reason,
    )


def _title(mode: ReviewMode) -> str:
    match mode:
        case ReviewMode.NONE:
            return RULES_ONLY_TITLE
        case ReviewMode.RECORDED:
            return RECORDED_TITLE
        case ReviewMode.OPENAI:
            return LIVE_TITLE
        case _:
            assert_never(mode)


def _colored(status: Status, color: ColorSetting) -> str:
    match color:
        case ColorSetting.ON:
            return f"{_status_color(status)}{status.value}{RESET}"
        case ColorSetting.OFF:
            return status.value
        case _:
            assert_never(color)


def _model_rebook_reason(outcome: ModelRebook) -> str:
    if outcome.best_offer_id is None:
        return MODEL_REBOOK_REASON
    return f"{MODEL_REBOOK_REASON} {outcome.best_offer_id} saves more."


def _first_sentence(text: str) -> str:
    sentence, separator, _ = text.partition(". ")
    return f"{sentence}." if separator else text


def _status_color(status: Status) -> str:
    match status:
        case Status.REBOOK:
            return GREEN
        case Status.KEEP | Status.NEEDS_REVIEW:
            return YELLOW
        case Status.INVALID_DATA | Status.INCOMPLETE_ANALYSIS:
            return RED
        case _:
            assert_never(status)
