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
)
from fare_reshop_agent.reshopping.orchestration.review import ReviewReport

EMPTY_CELL = "-"
COLUMN_GAP = "  "
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


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
    show_flags = any(row.trace is not None for row in report.results)
    ref_width = max(len(row.ref) for row in every_row)
    status_width = max(len(row.status) for row in every_row)
    offer_width = max(len(row.offer) for row in every_row)
    saving_width = max(len(row.saving) for row in every_row)
    flags_width = max(len(row.flags) for row in every_row)

    def line(row: _Row, status: str) -> str:
        flags = [row.flags.ljust(flags_width)] if show_flags else []
        return COLUMN_GAP.join(
            [
                row.ref.ljust(ref_width),
                status + " " * (status_width - len(row.status)),
                row.offer.ljust(offer_width),
                row.saving.ljust(saving_width),
                *flags,
                row.reason,
            ]
        )

    lines = [line(HEADER, HEADER.status)]
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
        case Rebook() | ModelRebook():
            offer: str = outcome.offer_id
            saving, reason = str(outcome.nominal_saving), EMPTY_CELL
            flags = outcome.approval_flags
        case NeedsReview():
            offer = outcome.offer_id or EMPTY_CELL
            saving = EMPTY_CELL if outcome.nominal_saving is None else str(outcome.nominal_saving)
            reason = _first_sentence(outcome.reasoning)
            flags = outcome.approval_flags
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


def _colored(status: Status, color: ColorSetting) -> str:
    match color:
        case ColorSetting.ON:
            return f"{_status_color(status)}{status.value}{RESET}"
        case ColorSetting.OFF:
            return status.value
        case _:
            assert_never(color)


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
