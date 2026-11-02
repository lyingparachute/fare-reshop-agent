from dataclasses import dataclass
from typing import assert_never

from fare_reshop_agent.reshopping.composition.color import ColorSetting
from fare_reshop_agent.reshopping.domain.recommendation import (
    Invalid,
    Keep,
    Rebook,
    Recommendation,
    Status,
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
    reason: str


HEADER = _Row(ref="PNR", status="STATUS", offer="OFFER", saving="SAVING", reason="REASON")


def render_table(report: ReviewReport, color: ColorSetting) -> str:
    rows = [_row(result) for result in report.results]
    every_row = [HEADER, *rows]
    ref_width = max(len(row.ref) for row in every_row)
    status_width = max(len(row.status) for row in every_row)
    offer_width = max(len(row.offer) for row in every_row)
    saving_width = max(len(row.saving) for row in every_row)

    def line(row: _Row, status: str) -> str:
        return COLUMN_GAP.join(
            [
                row.ref.ljust(ref_width),
                status + " " * (status_width - len(row.status)),
                row.offer.ljust(offer_width),
                row.saving.ljust(saving_width),
                row.reason,
            ]
        )

    lines = [line(HEADER, HEADER.status)]
    lines.extend(
        line(row, _colored(result.status, color))
        for row, result in zip(rows, report.results, strict=True)
    )
    lines.extend(
        f"data issue: {issue.kind} {issue.record_id}: {issue.reason}"
        for issue in report.data_issues
    )
    return "\n".join(lines)


def _row(result: Recommendation) -> _Row:
    match result:
        case Rebook():
            offer: str = result.offer_id
            saving, reason = str(result.nominal_saving), EMPTY_CELL
        case Keep():
            offer, saving, reason = EMPTY_CELL, EMPTY_CELL, _first_sentence(result.reasoning)
        case Invalid():
            offer, saving, reason = EMPTY_CELL, EMPTY_CELL, result.reason
        case _:
            assert_never(result)
    return _Row(
        ref=result.ref, status=result.status.value, offer=offer, saving=saving, reason=reason
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
        case Status.KEEP:
            return YELLOW
        case Status.INVALID_DATA:
            return RED
        case _:
            assert_never(status)
