from collections.abc import Mapping, Sequence
from decimal import Decimal

from fare_reshop_agent.reshopping.orchestration.agent_model import (
    FinalText,
    ModelReply,
    ToolCallRequest,
    ToolCalls,
    Transcript,
    Usage,
)
from fare_reshop_agent.reshopping.orchestration.canonical_json import JsonValue, canonical_json

TURN_USAGE = Usage(input_tokens=100, output_tokens=20)


class ScriptedModel:
    def __init__(self, scripts: Mapping[str, Sequence[ModelReply]]) -> None:
        self._scripts = {ref: tuple(replies) for ref, replies in scripts.items()}
        self.shown: list[Transcript] = []

    @property
    def model_name(self) -> str:
        return "scripted"

    def next_step(self, transcript: Transcript) -> ModelReply:
        self.shown.append(transcript)
        return self._scripts[transcript.booking_ref][transcript.turn - 1]

    def shown_for(self, ref: str) -> list[Transcript]:
        return [transcript for transcript in self.shown if transcript.booking_ref == ref]


def call(name: str, arguments: str = "{}") -> ToolCallRequest:
    return ToolCallRequest(name=name, arguments=arguments)


def calls(*requests: ToolCallRequest, text: str | None = None) -> ToolCalls:
    return ToolCalls(calls=requests, text=text, usage=TURN_USAGE)


def final(answer: dict[str, JsonValue]) -> FinalText:
    return FinalText(text=canonical_json(answer), usage=TURN_USAGE)


def rebook(offer_id: str, reasoning: str = "Cheaper fare, same flight.") -> FinalText:
    return final(
        {
            "decision": "rebook",
            "offer_id": offer_id,
            "reasoning": reasoning,
            "confidence": Decimal("0.82"),
        }
    )


def keep(reasoning: str = "The saving is not worth the change.") -> FinalText:
    return final(
        {"decision": "keep", "offer_id": None, "reasoning": reasoning, "confidence": Decimal("0.6")}
    )
