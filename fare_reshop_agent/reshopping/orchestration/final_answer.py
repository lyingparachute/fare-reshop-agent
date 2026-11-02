from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from fare_reshop_agent.reshopping.domain.trip import OfferId
from fare_reshop_agent.reshopping.orchestration.canonical_json import JsonValue
from fare_reshop_agent.reshopping.orchestration.model_json import (
    Malformed,
    is_text,
    parse_json_object,
)

FINAL_ANSWER_NAME = "review_decision"
FINAL_ANSWER_KEYS = ("decision", "offer_id", "reasoning", "confidence")


class Decision(StrEnum):
    REBOOK = "rebook"
    KEEP = "keep"


def final_answer_schema() -> dict[str, JsonValue]:
    return {
        "type": "object",
        "properties": {
            "decision": {"type": "string", "enum": [decision.value for decision in Decision]},
            "offer_id": {"type": ["string", "null"]},
            "reasoning": {"type": "string"},
            "confidence": {"type": "number"},
        },
        "required": list(FINAL_ANSWER_KEYS),
        "additionalProperties": False,
    }


@dataclass(frozen=True, slots=True, kw_only=True)
class RebookAnswer:
    offer_id: OfferId
    reasoning: str
    confidence: Decimal


@dataclass(frozen=True, slots=True, kw_only=True)
class KeepAnswer:
    reasoning: str
    confidence: Decimal


type FinalAnswer = RebookAnswer | KeepAnswer


def parse_final_answer(text: str) -> FinalAnswer | Malformed:
    parsed = parse_json_object(text)
    if isinstance(parsed, Malformed):
        return parsed
    if set(parsed) != set(FINAL_ANSWER_KEYS):
        return Malformed(reason=f"the keys must be exactly {', '.join(FINAL_ANSWER_KEYS)}")
    rationale = _rationale(parsed["reasoning"], parsed["confidence"])
    if isinstance(rationale, Malformed):
        return rationale
    reasoning, confidence = rationale
    offer_id = parsed["offer_id"]
    match parsed["decision"]:
        case Decision.REBOOK if is_text(offer_id) and offer_id:
            return RebookAnswer(
                offer_id=OfferId(offer_id), reasoning=reasoning, confidence=confidence
            )
        case Decision.KEEP if offer_id is None:
            return KeepAnswer(reasoning=reasoning, confidence=confidence)
        case _:
            return Malformed(reason="decision must be rebook with an offer_id or keep with null")


def _rationale(reasoning: JsonValue, confidence: JsonValue) -> tuple[str, Decimal] | Malformed:
    if not is_text(reasoning) or not reasoning:
        return Malformed(reason="reasoning must be non-empty text")
    if not isinstance(confidence, Decimal) or not confidence.is_finite():
        return Malformed(reason="confidence must be a finite number")
    if not 0 <= confidence <= 1:
        return Malformed(reason="confidence must be from 0 to 1")
    return reasoning, confidence
