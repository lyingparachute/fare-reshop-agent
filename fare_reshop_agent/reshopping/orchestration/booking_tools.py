from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import assert_never

from fare_reshop_agent.reshopping.domain.evaluation import OfferEvaluation, evaluate_offer
from fare_reshop_agent.reshopping.domain.exchange_rate import NoRate, RateUsage
from fare_reshop_agent.reshopping.domain.money import Money
from fare_reshop_agent.reshopping.domain.port.exchange_rates import ExchangeRates
from fare_reshop_agent.reshopping.domain.terms import BookingTerms
from fare_reshop_agent.reshopping.domain.trip import Offer, offers_on_route
from fare_reshop_agent.reshopping.orchestration.agent_model import ToolCallRequest, ToolSpec
from fare_reshop_agent.reshopping.orchestration.canonical_json import (
    TEXT_ENCODING,
    JsonValue,
    canonical_json,
)
from fare_reshop_agent.reshopping.orchestration.model_json import (
    Malformed,
    is_text,
    parse_json_object,
)


class ToolName(StrEnum):
    GET_BOOKING = "get_booking"
    SEARCH_OFFERS = "search_offers"
    CHECK_OFFER = "check_offer"


OFFER_ID_ARGUMENT = "offer_id"


class ToolErrorCode(StrEnum):
    BAD_ARGUMENTS = "bad_arguments"
    UNKNOWN_OFFER = "unknown_offer"
    UNKNOWN_TOOL = "unknown_tool"


_ERROR_TEXT = MappingProxyType(
    {
        ToolErrorCode.BAD_ARGUMENTS: (
            "Arguments for {value} are not valid.",
            "Send a JSON object with exactly the keys in the tool's spec, each of the right type.",
        ),
        ToolErrorCode.UNKNOWN_OFFER: (
            "Offer {value} is not on this booking's route and date.",
            "Pick an offer_id from search_offers.",
        ),
        ToolErrorCode.UNKNOWN_TOOL: (
            "There is no tool named {value}.",
            "Use one of: " + ", ".join(ToolName) + ".",
        ),
    }
)


def tool_specs() -> tuple[ToolSpec, ...]:
    return (
        ToolSpec(
            name=ToolName.GET_BOOKING,
            description="Return the booked trip under review: route, times, cabin, fare and fees.",
            parameters=_object_schema({}),
        ),
        ToolSpec(
            name=ToolName.SEARCH_OFFERS,
            description="Return the fares on sale now on the booking's route and date.",
            parameters=_object_schema({}),
        ),
        ToolSpec(
            name=ToolName.CHECK_OFFER,
            description=(
                "Return the rule results, nominal saving, approval flags and eligibility"
                " of one offer for this booking."
            ),
            parameters=_object_schema({OFFER_ID_ARGUMENT: {"type": "string"}}),
        ),
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolResult:
    ok: bool
    text: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BookingTools:
    terms: BookingTerms
    offers: tuple[Offer, ...]
    rates: ExchangeRates

    @classmethod
    def for_booking(
        cls, terms: BookingTerms, offers: Sequence[Offer], rates: ExchangeRates
    ) -> "BookingTools":
        return cls(terms=terms, offers=offers_on_route(offers, terms.booking), rates=rates)

    def run(self, call: ToolCallRequest) -> ToolResult:
        if call.name not in tuple(ToolName):
            return _failure(ToolErrorCode.UNKNOWN_TOOL, call.name)
        tool = ToolName(call.name)
        arguments = parse_json_object(call.arguments)
        if isinstance(arguments, Malformed) or set(arguments) != _argument_names(tool):
            return _failure(ToolErrorCode.BAD_ARGUMENTS, tool)
        match tool:
            case ToolName.GET_BOOKING:
                return _success(self._booking())
            case ToolName.SEARCH_OFFERS:
                return _success({"offers": [_offer(offer) for offer in self.offers]})
            case ToolName.CHECK_OFFER:
                return self._check_offer(arguments[OFFER_ID_ARGUMENT])
            case _:
                assert_never(tool)

    def _check_offer(self, offer_id: JsonValue) -> ToolResult:
        if not is_text(offer_id):
            return _failure(ToolErrorCode.BAD_ARGUMENTS, ToolName.CHECK_OFFER)
        offer = next((o for o in self.offers if o.offer_id == offer_id), None)
        if offer is None:
            return _failure(ToolErrorCode.UNKNOWN_OFFER, offer_id)
        return _success(self._check(offer))

    def _booking(self) -> dict[str, JsonValue]:
        booking = self.terms.booking
        return {
            "pnr": booking.ref,
            "passengers": booking.passengers,
            "origin": booking.origin,
            "destination": booking.destination,
            "departure_date": booking.departure.date().isoformat(),
            "departure": booking.departure.isoformat(),
            "carrier": booking.carrier,
            "flight_number": booking.flight_number,
            "cabin": booking.cabin.value,
            "refundable": booking.refundable,
            "baggage_pieces": booking.checked_bags,
            "stops": booking.stops,
            "price_per_passenger": _money(booking.price_per_passenger),
            "total_paid": _money(booking.total_paid),
            "change_fee_per_passenger": _money(booking.change_fee_per_passenger),
        }

    def _check(self, offer: Offer) -> dict[str, JsonValue]:
        evaluation = evaluate_offer(self.terms, offer, self.rates)
        minimum = self.terms.minimum.money
        return {
            "offer_id": evaluation.offer_id,
            "rules": [
                {"rule": r.rule.value, "result": r.outcome.value, "reason": r.reason}
                for r in evaluation.rules
            ],
            "nominal_saving": _saving(evaluation),
            "approval_flags": [flag.value for flag in evaluation.approval_flags],
            "exchange_rates": [_rate(usage) for usage in evaluation.rates],
            "minimum_saving": _money(minimum),
            "eligible": evaluation.is_eligible(minimum),
        }


def _offer(offer: Offer) -> dict[str, JsonValue]:
    return {
        "offer_id": offer.offer_id,
        "origin": offer.origin,
        "destination": offer.destination,
        "departure_date": offer.departure.date().isoformat(),
        "departure": offer.departure.isoformat(),
        "carrier": offer.carrier,
        "flight_number": offer.flight_number,
        "cabin": offer.cabin.value,
        "refundable": offer.refundable,
        "baggage_pieces": offer.checked_bags,
        "stops": offer.stops,
        "seats_available": offer.seats_available,
        "price_per_passenger": _money(offer.price),
        "change_fee_per_passenger": _money(offer.change_fee_per_passenger),
    }


def _saving(evaluation: OfferEvaluation) -> JsonValue:
    saving = evaluation.nominal_saving
    return None if isinstance(saving, NoRate) else _money(saving)


def _money(money: Money) -> dict[str, JsonValue]:
    return {"amount": format(money.rounded().amount, "f"), "currency": money.currency.code}


def _rate(usage: RateUsage) -> dict[str, JsonValue]:
    return {
        "use": usage.use.value,
        "rate": str(usage.rate.rate),
        "direction": usage.rate.direction,
        "as_of": usage.rate.as_of.isoformat(),
    }


def _argument_names(tool: ToolName) -> set[str]:
    match tool:
        case ToolName.GET_BOOKING | ToolName.SEARCH_OFFERS:
            return set()
        case ToolName.CHECK_OFFER:
            return {OFFER_ID_ARGUMENT}
        case _:
            assert_never(tool)


def _failure(code: ToolErrorCode, value: str) -> ToolResult:
    message, hint = _ERROR_TEXT[code]
    error: dict[str, JsonValue] = {
        "code": code.value,
        "message": message.format(value=_readable(value)),
        "hint": hint,
    }
    return ToolResult(ok=False, text=canonical_json({"ok": False, "error": error}))


def _readable(value: str) -> str:
    return value.encode(TEXT_ENCODING, errors="replace").decode(TEXT_ENCODING)


def _success(data: dict[str, JsonValue]) -> ToolResult:
    return ToolResult(ok=True, text=canonical_json({"ok": True, "data": data, "hint": None}))


def _object_schema(properties: dict[str, JsonValue]) -> dict[str, JsonValue]:
    required: list[JsonValue] = [*sorted(properties)]
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
