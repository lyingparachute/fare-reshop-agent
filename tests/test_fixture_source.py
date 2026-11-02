import json
import shutil
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pytest

from fare_reshop_agent.reshopping.domain.port.reshop_source import (
    DataIssueKind,
    RejectedBooking,
    ReshopSnapshot,
)
from fare_reshop_agent.reshopping.domain.trip import Booking
from fare_reshop_agent.reshopping.infrastructure.file_problem import FileProblem
from fare_reshop_agent.reshopping.infrastructure.json_fixtures.source import (
    JsonFixtureError,
    JsonFixtureSource,
)

from sample_data import REPO_FIXTURES, usd

SAMPLE_BOOKINGS = 5
SAMPLE_OFFERS = 6

type JsonObject = dict[str, object]


def copied_fixtures(tmp_path: Path) -> Path:
    folder = tmp_path / "fixtures"
    folder.mkdir(parents=True)
    for name in ("pnrs.json", "fares_feed.json"):
        shutil.copyfile(REPO_FIXTURES / name, folder / name)
    return folder


def edit_json(path: Path, change: Callable[[JsonObject], None]) -> None:
    document = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    change(document)
    path.write_text(json.dumps(document, default=exact_float), encoding="utf-8")


def exact_float(value: object) -> float:
    if not isinstance(value, Decimal):
        raise TypeError(f"cannot write {value!r} as JSON")
    number = float(value)
    if Decimal(repr(number)) != value:
        raise ValueError(f"{value} would lose digits as a JSON float; edit the text instead")
    return number


def copy_record(record: JsonObject) -> JsonObject:
    copied = json.loads(json.dumps(record, default=exact_float), parse_float=Decimal)
    assert isinstance(copied, dict)
    return copied


def nested(record: JsonObject, *keys: str) -> JsonObject:
    for key in keys:
        found = record[key]
        assert isinstance(found, dict)
        record = found
    return record


def records(document: JsonObject, key: str) -> list[JsonObject]:
    found = document[key]
    assert isinstance(found, list)
    return found


def first_booking(document: JsonObject) -> JsonObject:
    return records(document, "pnrs")[0]


def first_offer(document: JsonObject) -> JsonObject:
    return records(document, "offers")[0]


def snapshot_with(
    tmp_path: Path, file_name: str, change: Callable[[JsonObject], None]
) -> ReshopSnapshot:
    folder = copied_fixtures(tmp_path)
    edit_json(folder / file_name, change)
    return JsonFixtureSource(folder).read_snapshot()


def rejected_bookings(snapshot: ReshopSnapshot) -> list[RejectedBooking]:
    return [b for b in snapshot.bookings if isinstance(b, RejectedBooking)]


def issue_kinds(snapshot: ReshopSnapshot) -> list[tuple[DataIssueKind, str]]:
    return [(issue.kind, issue.record_id) for issue in snapshot.data_issues]


def test_fixture_money_is_read_as_exact_decimal(tmp_path: Path) -> None:
    folder = copied_fixtures(tmp_path)
    path = folder / "fares_feed.json"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace('"amount": 300.00', '"amount": 1234567.123456789', 1), encoding="utf-8"
    )

    offers = JsonFixtureSource(folder).read_snapshot().offers

    assert offers[0].price.amount == Decimal("1234567.123456789")
    assert str(offers[0].price.amount) == "1234567.123456789"


def test_malformed_booking_is_rejected_with_reason(tmp_path: Path) -> None:
    def change(document: JsonObject) -> None:
        first_booking(document)["passengers"] = "two"

    snapshot = snapshot_with(tmp_path, "pnrs.json", change)

    rejected = rejected_bookings(snapshot)
    assert [r.ref for r in rejected] == ["QX7T2A"]
    assert "passengers" in rejected[0].reason
    assert sum(isinstance(b, Booking) for b in snapshot.bookings) == SAMPLE_BOOKINGS - 1


def test_multi_segment_booking_is_rejected(tmp_path: Path) -> None:
    def change(document: JsonObject) -> None:
        itinerary = first_booking(document)["itinerary"]
        assert isinstance(itinerary, list)
        itinerary.append(itinerary[0])

    rejected = rejected_bookings(snapshot_with(tmp_path, "pnrs.json", change))

    assert [r.ref for r in rejected] == ["QX7T2A"]
    assert "2 segments" in rejected[0].reason


def test_bad_offer_is_listed_in_data_issues(tmp_path: Path) -> None:
    def change(document: JsonObject) -> None:
        first_offer(document)["price"] = "abc"

    snapshot = snapshot_with(tmp_path, "fares_feed.json", change)

    assert issue_kinds(snapshot) == [(DataIssueKind.OFFER_REJECTED, "OF-1001")]
    assert "OF-1001" not in {offer.offer_id for offer in snapshot.offers}


def test_duplicate_offer_ids_are_all_left_out(tmp_path: Path) -> None:
    def change(document: JsonObject) -> None:
        records(document, "offers")[1]["offerId"] = "OF-1001"

    snapshot = snapshot_with(tmp_path, "fares_feed.json", change)

    assert "OF-1001" not in {offer.offer_id for offer in snapshot.offers}
    assert len(snapshot.offers) == SAMPLE_OFFERS - 2
    assert issue_kinds(snapshot) == [
        (DataIssueKind.OFFER_DUPLICATE, "OF-1001"),
        (DataIssueKind.OFFER_DUPLICATE, "OF-1001"),
    ]


def test_duplicate_booking_keeps_first_record(tmp_path: Path) -> None:
    def change(document: JsonObject) -> None:
        copy = copy_record(first_booking(document))
        nested(copy, "ticket", "pricePerPassenger")["amount"] = 999
        records(document, "pnrs").append(copy)

    snapshot = snapshot_with(tmp_path, "pnrs.json", change)

    kept = [b for b in snapshot.bookings if isinstance(b, Booking) and b.ref == "QX7T2A"]
    assert [b.price_per_passenger for b in kept] == [usd("480.00")]
    assert issue_kinds(snapshot) == [(DataIssueKind.BOOKING_DUPLICATE, "QX7T2A")]


def test_unknown_field_rejects_that_record(tmp_path: Path) -> None:
    def change(document: JsonObject) -> None:
        first_booking(document)["notes"] = "window seat"

    rejected = rejected_bookings(snapshot_with(tmp_path, "pnrs.json", change))

    assert [r.ref for r in rejected] == ["QX7T2A"]
    assert "notes" in rejected[0].reason


def test_comment_key_is_ignored() -> None:
    snapshot = JsonFixtureSource(REPO_FIXTURES).read_snapshot()

    assert len(snapshot.bookings) == SAMPLE_BOOKINGS
    assert all(isinstance(b, Booking) for b in snapshot.bookings)
    assert len(snapshot.offers) == SAMPLE_OFFERS
    assert snapshot.data_issues == ()


def test_negative_stops_bags_or_seats_rejects_record(tmp_path: Path) -> None:
    cases: list[tuple[str, Callable[[JsonObject], None]]] = [
        ("stops", lambda d: first_offer(d).__setitem__("stops", -1)),
        ("bags", lambda d: first_offer(d).__setitem__("baggageIncludedPieces", -1)),
        ("seats", lambda d: first_offer(d).__setitem__("seatsAvailable", -1)),
    ]
    for name, change in cases:
        snapshot = snapshot_with(tmp_path / name, "fares_feed.json", change)

        assert issue_kinds(snapshot) == [(DataIssueKind.OFFER_REJECTED, "OF-1001")], name


def test_comment_inside_a_record_is_unknown_key(tmp_path: Path) -> None:
    def change(document: JsonObject) -> None:
        first_offer(document)["_comment"] = "a note"

    snapshot = snapshot_with(tmp_path, "fares_feed.json", change)

    assert issue_kinds(snapshot) == [(DataIssueKind.OFFER_REJECTED, "OF-1001")]


def test_missing_fixture_raises_json_fixture_error(tmp_path: Path) -> None:
    with pytest.raises(JsonFixtureError) as raised:
        JsonFixtureSource(tmp_path / "nowhere").read_snapshot()

    assert raised.value.problem is FileProblem.MISSING


def test_offer_with_route_date_unlike_its_departure_is_rejected(tmp_path: Path) -> None:
    def change(document: JsonObject) -> None:
        route = first_offer(document)["route"]
        assert isinstance(route, dict)
        route["departureDate"] = "2026-08-16"

    snapshot = snapshot_with(tmp_path, "fares_feed.json", change)

    assert issue_kinds(snapshot) == [(DataIssueKind.OFFER_REJECTED, "OF-1001")]


@pytest.mark.parametrize(
    ("file_name", "text", "fact"),
    [
        ("pnrs.json", "{not json", "Expecting property name"),
        ("pnrs.json", '{"_comment": "no bookings key"}', "pnrs: Field required"),
        ("fares_feed.json", '{"capturedAt": "2026-07-08T09:00:00", "offers": []}', "capturedAt"),
    ],
)
def test_malformed_fixture_file_raises_json_fixture_error(
    tmp_path: Path, file_name: str, text: str, fact: str
) -> None:
    folder = copied_fixtures(tmp_path)
    (folder / file_name).write_text(text, encoding="utf-8")

    with pytest.raises(JsonFixtureError, match=fact) as raised:
        JsonFixtureSource(folder).read_snapshot()

    assert raised.value.problem is FileProblem.MALFORMED


def test_unreadable_fixture_raises_json_fixture_error(tmp_path: Path) -> None:
    folder = copied_fixtures(tmp_path)
    (folder / "pnrs.json").unlink()
    (folder / "pnrs.json").mkdir()

    with pytest.raises(JsonFixtureError) as raised:
        JsonFixtureSource(folder).read_snapshot()

    assert raised.value.problem is FileProblem.UNREADABLE


def test_records_without_readable_id_are_listed_by_position(tmp_path: Path) -> None:
    folder = copied_fixtures(tmp_path)
    edit_json(folder / "pnrs.json", lambda d: first_booking(d).__setitem__("pnr", ""))
    edit_json(folder / "fares_feed.json", lambda d: first_offer(d).__delitem__("offerId"))

    snapshot = JsonFixtureSource(folder).read_snapshot()

    assert issue_kinds(snapshot) == [
        (DataIssueKind.BOOKING_REJECTED, "pnrs[0]"),
        (DataIssueKind.OFFER_REJECTED, "offers[0]"),
    ]


def test_departure_must_be_a_full_local_time(tmp_path: Path) -> None:
    def change(document: JsonObject) -> None:
        itinerary = first_booking(document)["itinerary"]
        assert isinstance(itinerary, list)
        itinerary[0]["departure"] = "2026-08-15"

    rejected = rejected_bookings(snapshot_with(tmp_path, "pnrs.json", change))

    assert [r.ref for r in rejected] == ["QX7T2A"]
    assert "is not a time like 2026-08-15T08:00:00" in rejected[0].reason


@pytest.mark.parametrize(
    ("file_name", "field", "text", "rejected_id"),
    [
        ("pnrs.json", "departure", "2026-8-15T8:0:0", "QX7T2A"),
        ("fares_feed.json", "departure", "2026-8-15T8:00:00", "OF-1001"),
        ("fares_feed.json", "departureDate", "2026-8-15", "OF-1001"),
    ],
)
def test_times_without_zero_padding_are_rejected(
    tmp_path: Path, file_name: str, field: str, text: str, rejected_id: str
) -> None:
    def change(document: JsonObject) -> None:
        if file_name == "pnrs.json":
            itinerary = first_booking(document)["itinerary"]
            assert isinstance(itinerary, list)
            itinerary[0][field] = text
        elif field == "departureDate":
            nested(first_offer(document), "route")[field] = text
        else:
            first_offer(document)[field] = text

    snapshot = snapshot_with(tmp_path, file_name, change)

    rejected_ids = [r.ref for r in rejected_bookings(snapshot)] + [
        issue.record_id for issue in snapshot.data_issues
    ]
    assert rejected_ids == [rejected_id]


def test_capture_time_without_zero_padding_is_malformed(tmp_path: Path) -> None:
    folder = copied_fixtures(tmp_path)
    edit_json(
        folder / "fares_feed.json", lambda d: d.__setitem__("capturedAt", "2026-07-08T9:00:00Z")
    )

    with pytest.raises(JsonFixtureError, match="capturedAt"):
        JsonFixtureSource(folder).read_snapshot()
