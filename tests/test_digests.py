import dataclasses
import json
from datetime import date
from decimal import Decimal

import pytest

from fare_reshop_agent.reshopping.domain.exchange_rate import ExchangeRate
from fare_reshop_agent.reshopping.domain.money import Money
from fare_reshop_agent.reshopping.domain.port.reshop_source import RejectedBooking, ReshopSnapshot
from fare_reshop_agent.reshopping.domain.terms import ReviewPolicy
from fare_reshop_agent.reshopping.domain.trip import BookingRef, OfferId
from fare_reshop_agent.reshopping.infrastructure.json_fixtures.source import JsonFixtureSource
from fare_reshop_agent.reshopping.orchestration.agent_model import (
    Prompt,
    ToolCallItem,
    ToolResultItem,
    ToolSpec,
    Transcript,
    UserMessage,
)
from fare_reshop_agent.reshopping.orchestration.booking_tools import tool_specs
from fare_reshop_agent.reshopping.orchestration.canonical_json import JsonValue, canonical_json
from fare_reshop_agent.reshopping.orchestration.digests import (
    digest,
    fares_feed_projection,
    money_projection,
    pnrs_projection,
    policy_projection,
    rates_projection,
    tools_projection,
    transcript_digest,
    transcript_projection,
)

from sample_data import (
    EUR,
    EUR_USD,
    GBP,
    OF_1001,
    REPO_FIXTURES,
    USD,
    sample_booking,
    usd,
    with_bookings,
)

PINNED_TRANSCRIPT = Transcript(
    booking_ref=BookingRef("QX7T2A"),
    turn=2,
    prompt=Prompt(data=b"Pick a fare."),
    tool_specs=(
        ToolSpec(
            name="get_booking",
            description="Read the booking.",
            parameters={"type": "object", "properties": {}, "required": []},
        ),
    ),
    items=(
        UserMessage(text="Review booking QX7T2A."),
        ToolCallItem(call_id="call_1_1", name="get_booking", arguments="{}"),
        ToolResultItem(call_id="call_1_1", result='{"ok":true}'),
    ),
)


PINNED_TRANSCRIPT_TEXT = (
    '{"booking":"QX7T2A","instructions":"Pick a fare.","items":['
    '{"kind":"user","text":"Review booking QX7T2A."},'
    '{"arguments":"{}","call_id":"call_1_1","kind":"call","name":"get_booking"},'
    '{"call_id":"call_1_1","kind":"result","result":"{\\"ok\\":true}"}],'
    '"tools":[{"description":"Read the booking.","name":"get_booking",'
    '"parameters":{"properties":{},"required":[],"type":"object"}}],"turn":2}'
)


PINNED_TRANSCRIPT_DIGEST = "114bfffd73b385f5e618c86c96332d684ca4eea723ecf4ad519bf434a5a191dd"


def repo_snapshot() -> ReshopSnapshot:
    return JsonFixtureSource(REPO_FIXTURES).read_snapshot()


def test_canonical_json_refuses_floats() -> None:
    with pytest.raises(TypeError, match="float"):
        canonical_json({"offers": [{"price": json.loads("80.5")}]})


def test_canonical_json_ignores_key_order() -> None:
    first = canonical_json({"b": 1, "a": {"d": True, "c": None}})
    second = canonical_json({"a": {"c": None, "d": True}, "b": 1})

    assert first == second
    assert digest({"b": 1, "a": 2}) == digest({"a": 2, "b": 1})


def test_decimal_80_00_is_written_fixed_point() -> None:
    assert canonical_json(Decimal("80.00")) == "80.00"
    assert canonical_json(Decimal("80")) == "80"


def test_money_is_normalized_to_two_places() -> None:
    whole = Money(amount=Decimal("80"), currency=USD)
    cents = Money(amount=Decimal("80.00"), currency=USD)
    booking = sample_booking("QX7T2A")
    whole_fee = dataclasses.replace(booking, change_fee_per_passenger=whole)
    cents_fee = dataclasses.replace(booking, change_fee_per_passenger=cents)

    assert money_projection(whole) == {"amount": "80.00", "currency": "USD"}
    assert money_projection(whole) == money_projection(cents)
    assert digest(pnrs_projection(with_bookings(whole_fee))) == digest(
        pnrs_projection(with_bookings(cents_fee))
    )


def test_money_with_three_places_is_refused() -> None:
    with pytest.raises(ValueError, match=r"80\.005 USD"):
        money_projection(Money(amount=Decimal("80.005"), currency=USD))


def test_money_digit_change_changes_digest() -> None:
    snapshot = repo_snapshot()
    first, *others = snapshot.offers
    changed = dataclasses.replace(first, price=first.price + usd("0.01"))
    changed_snapshot = dataclasses.replace(snapshot, offers=(changed, *others))

    assert digest(fares_feed_projection(changed_snapshot)) != digest(
        fares_feed_projection(snapshot)
    )
    assert digest(pnrs_projection(changed_snapshot)) == digest(pnrs_projection(snapshot))


def test_digest_survives_field_rename() -> None:
    assert canonical_json(transcript_projection(PINNED_TRANSCRIPT)) == PINNED_TRANSCRIPT_TEXT
    assert transcript_digest(PINNED_TRANSCRIPT) == PINNED_TRANSCRIPT_DIGEST


def test_booking_and_offer_projections_pin_every_field() -> None:
    snapshot = dataclasses.replace(with_bookings(sample_booking("QX7T2A")), offers=(OF_1001,))

    assert pnrs_projection(snapshot) == {
        "bookings": [
            {
                "ref": "QX7T2A",
                "passengers": 1,
                "origin": "JFK",
                "destination": "LAX",
                "departure": "2026-08-15T08:00:00",
                "arrival": "2026-08-15T11:20:00",
                "carrier": "AA",
                "flight_number": "AA118",
                "stops": 0,
                "cabin": "ECONOMY",
                "price_per_passenger": {"amount": "480.00", "currency": "USD"},
                "total_paid": {"amount": "480.00", "currency": "USD"},
                "refundable": False,
                "change_fee_per_passenger": {"amount": "100.00", "currency": "USD"},
                "checked_bags": 1,
            }
        ],
        "rejected": [],
    }
    assert fares_feed_projection(snapshot) == {
        "capture_time": "2026-07-08T09:00:00+00:00",
        "offers": [
            {
                "offer_id": "OF-1001",
                "origin": "JFK",
                "destination": "LAX",
                "departure": "2026-08-15T08:00:00",
                "arrival": "2026-08-15T11:20:00",
                "carrier": "AA",
                "flight_number": "AA118",
                "stops": 0,
                "cabin": "ECONOMY",
                "price": {"amount": "300.00", "currency": "USD"},
                "refundable": False,
                "change_fee_per_passenger": {"amount": "100.00", "currency": "USD"},
                "checked_bags": 1,
                "seats_available": 5,
            }
        ],
    }


def field_of(entries: JsonValue, key: str) -> list[JsonValue]:
    assert isinstance(entries, list)
    values: list[JsonValue] = []
    for entry in entries:
        assert isinstance(entry, dict)
        values.append(entry[key])
    return values


def test_projections_sort_their_entries() -> None:
    late_offer = dataclasses.replace(OF_1001, offer_id=OfferId("OF-9000"))
    snapshot = dataclasses.replace(
        with_bookings(
            sample_booking("ZC3N1D"),
            RejectedBooking(ref=BookingRef("ZZ0000"), reason="bad"),
            sample_booking("HB6W9E"),
            RejectedBooking(ref=BookingRef("AA0000"), reason="bad"),
        ),
        offers=(late_offer, OF_1001),
    )
    gbp_rate = ExchangeRate(base=GBP, quote=USD, rate=Decimal("1.27"), as_of=date(2026, 7, 7))
    specs = tuple(reversed(tool_specs()))

    pnrs = pnrs_projection(snapshot)
    feed = fares_feed_projection(snapshot)
    rates = rates_projection([gbp_rate, EUR_USD])
    tools = tools_projection(specs)

    assert field_of(pnrs["bookings"], "ref") == ["HB6W9E", "ZC3N1D"]
    assert pnrs["rejected"] == ["AA0000", "ZZ0000"]
    assert field_of(feed["offers"], "offer_id") == ["OF-1001", "OF-9000"]
    assert field_of(rates, "base") == ["EUR", "GBP"]
    assert field_of(tools, "name") == ["check_offer", "get_booking", "search_offers"]


def test_policy_projection_writes_minimum_in_its_currency() -> None:
    policy = ReviewPolicy(minimum_saving=Money(amount=Decimal("43.7"), currency=EUR))

    assert policy_projection(policy) == {"minimum_saving": {"amount": "43.70", "currency": "EUR"}}


def test_rates_projection_writes_fixed_point_rate() -> None:
    rate = ExchangeRate(base=EUR, quote=USD, rate=Decimal("1E-7"), as_of=date(2026, 7, 7))

    assert rates_projection([rate]) == [
        {"as_of": "2026-07-07", "base": "EUR", "quote": "USD", "rate": "0.0000001"}
    ]


def test_transcript_digest_covers_domain_transcript() -> None:
    other_result = dataclasses.replace(
        PINNED_TRANSCRIPT,
        items=(
            *PINNED_TRANSCRIPT.items[:2],
            ToolResultItem(call_id="call_1_1", result='{"ok":false}'),
        ),
    )
    other_turn = dataclasses.replace(PINNED_TRANSCRIPT, turn=3)

    assert transcript_digest(other_result) != transcript_digest(PINNED_TRANSCRIPT)
    assert transcript_digest(other_turn) != transcript_digest(PINNED_TRANSCRIPT)
