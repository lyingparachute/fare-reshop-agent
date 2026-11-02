import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import partial
from pathlib import Path

from pydantic import BaseModel, ValidationError

from fare_reshop_agent.reshopping.domain.money import Currency, Money
from fare_reshop_agent.reshopping.domain.port.reshop_source import (
    DataIssue,
    DataIssueKind,
    RejectedBooking,
    ReshopSnapshot,
)
from fare_reshop_agent.reshopping.domain.trip import Booking, BookingRef, Offer, OfferId
from fare_reshop_agent.reshopping.infrastructure.file_problem import (
    FileProblem,
    FileReadError,
    exact_time,
    read_model,
    validation_fact,
)
from fare_reshop_agent.reshopping.infrastructure.json_fixtures.records import (
    BookingKey,
    BookingRecord,
    BookingsFile,
    MoneyRecord,
    OfferKey,
    OfferRecord,
    OffersFile,
)

BOOKINGS_FILE = "pnrs.json"
OFFERS_FILE = "fares_feed.json"
CAPTURE_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
CAPTURE_TIME_EXAMPLE = "2026-07-08T09:00:00Z"
LOCAL_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"
LOCAL_TIME_EXAMPLE = "2026-08-15T08:00:00"
DATE_FORMAT = "%Y-%m-%d"
DATE_EXAMPLE = "2026-08-15"


class JsonFixtureError(FileReadError):
    pass


class JsonFixtureSource:
    def __init__(self, folder: Path) -> None:
        self._bookings_path = folder / BOOKINGS_FILE
        self._offers_path = folder / OFFERS_FILE

    def read_snapshot(self) -> ReshopSnapshot:
        bookings_file = _read_json(self._bookings_path, BookingsFile)
        offers_file = _read_json(self._offers_path, OffersFile)
        bookings, booking_issues = _read_bookings(bookings_file.pnrs)
        offers, offer_issues = _read_offers(offers_file.offers)
        return ReshopSnapshot(
            captured_at=_capture_time(self._offers_path, offers_file.captured_at),
            bookings=bookings,
            offers=offers,
            data_issues=booking_issues + offer_issues,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class _Rejection:
    reason: str


def _read_json[FileModel: BaseModel](path: Path, model: type[FileModel]) -> FileModel:
    return read_model(
        path,
        model,
        JsonFixtureError,
        partial(json.loads, parse_float=Decimal),
        json.JSONDecodeError,
    )


def _capture_time(path: Path, text: str) -> datetime:
    try:
        return exact_time(text, CAPTURE_TIME_FORMAT, CAPTURE_TIME_EXAMPLE).replace(tzinfo=UTC)
    except ValueError as err:
        raise JsonFixtureError(
            path=path,
            problem=FileProblem.MALFORMED,
            fact=f"capturedAt: {err}",
        ) from err


def _read_bookings(
    records: Sequence[object],
) -> tuple[tuple[Booking | RejectedBooking, ...], tuple[DataIssue, ...]]:
    bookings: list[Booking | RejectedBooking] = []
    issues: list[DataIssue] = []
    seen: set[str] = set()
    for position, record in enumerate(records):
        try:
            ref = BookingKey.model_validate(record).pnr
        except ValidationError:
            issues.append(
                DataIssue(
                    kind=DataIssueKind.BOOKING_REJECTED,
                    record_id=f"pnrs[{position}]",
                    reason="the booking has no readable pnr",
                )
            )
            continue
        if ref in seen:
            issues.append(
                DataIssue(
                    kind=DataIssueKind.BOOKING_DUPLICATE,
                    record_id=ref,
                    reason=f"a booking with pnr {ref} appears earlier in the file",
                )
            )
            continue
        seen.add(ref)
        match _booking(record):
            case Booking() as booking:
                bookings.append(booking)
            case _Rejection(reason=reason):
                bookings.append(RejectedBooking(ref=BookingRef(ref), reason=reason))
    return tuple(bookings), tuple(issues)


def _read_offers(records: Sequence[object]) -> tuple[tuple[Offer, ...], tuple[DataIssue, ...]]:
    keyed: list[tuple[int, str | None, object]] = []
    for position, record in enumerate(records):
        try:
            keyed.append((position, OfferKey.model_validate(record).offer_id, record))
        except ValidationError:
            keyed.append((position, None, record))
    copies = Counter(offer_id for _, offer_id, _ in keyed if offer_id is not None)
    offers: list[Offer] = []
    issues: list[DataIssue] = []
    for position, offer_id, record in keyed:
        if offer_id is None:
            issues.append(
                DataIssue(
                    kind=DataIssueKind.OFFER_REJECTED,
                    record_id=f"offers[{position}]",
                    reason="the offer has no readable offerId",
                )
            )
        elif copies[offer_id] > 1:
            issues.append(
                DataIssue(
                    kind=DataIssueKind.OFFER_DUPLICATE,
                    record_id=offer_id,
                    reason=f"offerId {offer_id} appears {copies[offer_id]} times",
                )
            )
        else:
            match _offer(record):
                case Offer() as offer:
                    offers.append(offer)
                case _Rejection(reason=reason):
                    issues.append(
                        DataIssue(
                            kind=DataIssueKind.OFFER_REJECTED, record_id=offer_id, reason=reason
                        )
                    )
    return tuple(offers), tuple(issues)


def _booking(record: object) -> Booking | _Rejection:
    parsed = _validate(BookingRecord, record)
    if isinstance(parsed, _Rejection):
        return parsed
    if len(parsed.itinerary) != 1:
        return _Rejection(
            reason=f"the itinerary has {len(parsed.itinerary)} segments; exactly one is supported"
        )
    segment = parsed.itinerary[0]
    ticket = parsed.ticket
    try:
        return Booking(
            ref=BookingRef(parsed.pnr),
            passengers=parsed.passengers,
            origin=segment.origin,
            destination=segment.destination,
            departure=_local_time(segment.departure),
            arrival=_local_time(segment.arrival),
            carrier=segment.carrier,
            stops=segment.stops,
            cabin=ticket.cabin,
            price_per_passenger=_money(ticket.price_per_passenger),
            total_paid=_money(ticket.total_paid),
            refundable=ticket.refundable,
            change_fee_per_passenger=_money(ticket.change_fee_per_passenger),
            checked_bags=ticket.baggage_included_pieces,
        )
    except ValueError as err:
        return _Rejection(reason=str(err))


def _offer(record: object) -> Offer | _Rejection:
    parsed = _validate(OfferRecord, record)
    if isinstance(parsed, _Rejection):
        return parsed
    try:
        offer = Offer(
            offer_id=OfferId(parsed.offer_id),
            origin=parsed.route.origin,
            destination=parsed.route.destination,
            departure=_local_time(parsed.departure),
            arrival=_local_time(parsed.arrival),
            carrier=parsed.carrier,
            stops=parsed.stops,
            cabin=parsed.cabin,
            price=_money(parsed.price),
            refundable=parsed.refundable,
            change_fee_per_passenger=_money(parsed.change_fee_per_passenger),
            checked_bags=parsed.baggage_included_pieces,
            seats_available=parsed.seats_available,
        )
        route_date = _date(parsed.route.departure_date)
    except ValueError as err:
        return _Rejection(reason=str(err))
    if route_date != offer.departure.date():
        return _Rejection(
            reason=f"route.departureDate {route_date} differs from the departure {offer.departure}"
        )
    return offer


def _validate[RecordModel: BaseModel](
    model: type[RecordModel], record: object
) -> RecordModel | _Rejection:
    try:
        return model.model_validate(record)
    except ValidationError as err:
        return _Rejection(reason=validation_fact(err))


def _money(record: MoneyRecord) -> Money:
    return Money.of(record.amount, Currency(code=record.currency))


def _local_time(text: str) -> datetime:
    return exact_time(text, LOCAL_TIME_FORMAT, LOCAL_TIME_EXAMPLE)


def _date(text: str) -> date:
    return exact_time(text, DATE_FORMAT, DATE_EXAMPLE).date()
