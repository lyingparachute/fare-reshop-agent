import hashlib
from collections.abc import Sequence
from typing import assert_never

from fare_reshop_agent.reshopping.domain.exchange_rate import ExchangeRate
from fare_reshop_agent.reshopping.domain.money import Money
from fare_reshop_agent.reshopping.domain.port.reshop_source import RejectedBooking, ReshopSnapshot
from fare_reshop_agent.reshopping.domain.terms import ReviewPolicy
from fare_reshop_agent.reshopping.domain.trip import Booking, Offer
from fare_reshop_agent.reshopping.orchestration.agent_model import (
    ToolCallItem,
    ToolResultItem,
    ToolSpec,
    Transcript,
    TranscriptItem,
    UserMessage,
)
from fare_reshop_agent.reshopping.orchestration.canonical_json import (
    TEXT_ENCODING,
    JsonValue,
    canonical_json,
)

MONEY_PLACES = 2


class MoneyTooPrecise(ValueError):
    pass


def digest(value: JsonValue) -> str:
    return hashlib.sha256(canonical_json(value).encode(TEXT_ENCODING)).hexdigest()


def transcript_digest(transcript: Transcript) -> str:
    return digest(transcript_projection(transcript))


def money_projection(money: Money) -> dict[str, JsonValue]:
    exponent = money.amount.as_tuple().exponent
    if not isinstance(exponent, int) or -exponent > MONEY_PLACES:
        raise MoneyTooPrecise(
            f"money in a digest has at most {MONEY_PLACES} decimal places,"
            f" got {money.amount} {money.currency}"
        )
    return {"amount": format(money.amount, f".{MONEY_PLACES}f"), "currency": money.currency.code}


def pnrs_projection(snapshot: ReshopSnapshot) -> dict[str, JsonValue]:
    bookings = sorted((b for b in snapshot.bookings if isinstance(b, Booking)), key=lambda b: b.ref)
    rejected = sorted(
        (b for b in snapshot.bookings if isinstance(b, RejectedBooking)), key=lambda b: b.ref
    )
    return {
        "bookings": [_booking(booking) for booking in bookings],
        "rejected": [booking.ref for booking in rejected],
    }


def fares_feed_projection(snapshot: ReshopSnapshot) -> dict[str, JsonValue]:
    offers = sorted(snapshot.offers, key=lambda offer: offer.offer_id)
    return {
        "capture_time": snapshot.captured_at.isoformat(),
        "offers": [_offer(offer) for offer in offers],
    }


def rates_projection(rates: Sequence[ExchangeRate]) -> list[JsonValue]:
    ordered = sorted(rates, key=lambda rate: (rate.base.code, rate.quote.code))
    return [
        {
            "base": rate.base.code,
            "quote": rate.quote.code,
            "rate": format(rate.rate, "f"),
            "as_of": rate.as_of.isoformat(),
        }
        for rate in ordered
    ]


def policy_projection(policy: ReviewPolicy) -> dict[str, JsonValue]:
    return {"minimum_saving": money_projection(policy.minimum_saving)}


def tools_projection(specs: Sequence[ToolSpec]) -> list[JsonValue]:
    ordered = sorted(specs, key=lambda spec: spec.name)
    return [
        {"name": spec.name, "description": spec.description, "parameters": spec.parameters}
        for spec in ordered
    ]


def transcript_projection(transcript: Transcript) -> dict[str, JsonValue]:
    return {
        "booking": transcript.booking_ref,
        "turn": transcript.turn,
        "instructions": transcript.prompt.text,
        "tools": tools_projection(transcript.tool_specs),
        "items": [_item(item) for item in transcript.items],
    }


def _booking(booking: Booking) -> JsonValue:
    return {
        "ref": booking.ref,
        "passengers": booking.passengers,
        "origin": booking.origin,
        "destination": booking.destination,
        "departure": booking.departure.isoformat(),
        "arrival": booking.arrival.isoformat(),
        "carrier": booking.carrier,
        "flight_number": booking.flight_number,
        "stops": booking.stops,
        "cabin": booking.cabin.value,
        "price_per_passenger": money_projection(booking.price_per_passenger),
        "total_paid": money_projection(booking.total_paid),
        "refundable": booking.refundable,
        "change_fee_per_passenger": money_projection(booking.change_fee_per_passenger),
        "checked_bags": booking.checked_bags,
    }


def _offer(offer: Offer) -> JsonValue:
    return {
        "offer_id": offer.offer_id,
        "origin": offer.origin,
        "destination": offer.destination,
        "departure": offer.departure.isoformat(),
        "arrival": offer.arrival.isoformat(),
        "carrier": offer.carrier,
        "flight_number": offer.flight_number,
        "stops": offer.stops,
        "cabin": offer.cabin.value,
        "price": money_projection(offer.price),
        "refundable": offer.refundable,
        "change_fee_per_passenger": money_projection(offer.change_fee_per_passenger),
        "checked_bags": offer.checked_bags,
        "seats_available": offer.seats_available,
    }


def _item(item: TranscriptItem) -> JsonValue:
    match item:
        case UserMessage():
            return {"kind": "user", "text": item.text}
        case ToolCallItem():
            return {
                "kind": "call",
                "call_id": item.call_id,
                "name": item.name,
                "arguments": item.arguments,
            }
        case ToolResultItem():
            return {"kind": "result", "call_id": item.call_id, "result": item.result}
        case _:
            assert_never(item)
