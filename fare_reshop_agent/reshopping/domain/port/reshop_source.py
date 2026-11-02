from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from fare_reshop_agent.reshopping.domain.trip import Booking, BookingRef, Offer


class DataIssueKind(StrEnum):
    BOOKING_REJECTED = "booking_rejected"
    OFFER_REJECTED = "offer_rejected"
    OFFER_DUPLICATE = "offer_duplicate"
    BOOKING_DUPLICATE = "booking_duplicate"


@dataclass(frozen=True, slots=True, kw_only=True)
class DataIssue:
    kind: DataIssueKind
    record_id: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RejectedBooking:
    ref: BookingRef
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ReshopSnapshot:
    captured_at: datetime
    bookings: tuple[Booking | RejectedBooking, ...]
    offers: tuple[Offer, ...]
    data_issues: tuple[DataIssue, ...]

    def __post_init__(self) -> None:
        if self.captured_at.utcoffset() != timedelta(0):
            raise ValueError(f"capture time must be in UTC, got {self.captured_at}")


class ReshopSource(Protocol):
    def read_snapshot(self) -> ReshopSnapshot: ...
