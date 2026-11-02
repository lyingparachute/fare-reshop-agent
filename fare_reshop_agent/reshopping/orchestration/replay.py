from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never

from fare_reshop_agent.reshopping.domain.trip import BookingRef
from fare_reshop_agent.reshopping.orchestration.agent_model import ModelReply, Transcript
from fare_reshop_agent.reshopping.orchestration.booking_loop import Trace
from fare_reshop_agent.reshopping.orchestration.digests import transcript_digest
from fare_reshop_agent.reshopping.orchestration.recording import (
    RecordedTurns,
    RecordingHeader,
)


class HeaderInput(StrEnum):
    PNRS = "pnrs"
    FARES_FEED = "fares_feed"
    POLICY = "policy"
    RATES = "rates"
    PROMPT = "prompt"
    TOOLS = "tools"


@dataclass(frozen=True, slots=True, kw_only=True)
class HeaderChanged:
    input: HeaderInput


@dataclass(frozen=True, slots=True, kw_only=True)
class DigestMismatch:
    booking: BookingRef
    turn: int


@dataclass(frozen=True, slots=True, kw_only=True)
class MissingTurn:
    booking: BookingRef
    turn: int


@dataclass(frozen=True, slots=True, kw_only=True)
class LeftoverTurn:
    booking: BookingRef
    turn: int


type StaleReason = HeaderChanged | DigestMismatch | MissingTurn | LeftoverTurn


class StaleRecording(Exception):
    def __init__(self, reasons: tuple[StaleReason, ...]) -> None:
        super().__init__(", ".join(type(reason).__name__ for reason in reasons))
        self.reasons = reasons


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordedTrace:
    trace: Trace
    recorded_model: str


def changed_inputs(current: RecordingHeader, recorded: RecordingHeader) -> tuple[HeaderInput, ...]:
    return tuple(
        header_input
        for header_input in HeaderInput
        if _digest(current, header_input) != _digest(recorded, header_input)
    )


def leftover_turns(
    recorded: RecordedTurns, turns_taken: Mapping[BookingRef, int]
) -> tuple[LeftoverTurn, ...]:
    ordered = sorted(recorded.turns, key=lambda turn: (turn.booking, turn.turn))
    return tuple(
        LeftoverTurn(booking=turn.booking, turn=turn.turn)
        for turn in ordered
        if turn.turn > turns_taken.get(turn.booking, 0)
    )


def _digest(header: RecordingHeader, header_input: HeaderInput) -> str:
    match header_input:
        case HeaderInput.PNRS:
            return header.pnrs
        case HeaderInput.FARES_FEED:
            return header.fares_feed
        case HeaderInput.POLICY:
            return header.policy
        case HeaderInput.RATES:
            return header.rates
        case HeaderInput.PROMPT:
            return header.prompt
        case HeaderInput.TOOLS:
            return header.tools
        case _:
            assert_never(header_input)


class RecordedModel:
    def __init__(self, recorded: RecordedTurns) -> None:
        self._model = recorded.model
        self._entries = {(turn.booking, turn.turn): turn for turn in recorded.turns}

    @property
    def model_name(self) -> str:
        return self._model

    def next_step(self, transcript: Transcript) -> ModelReply:
        key = (transcript.booking_ref, transcript.turn)
        entry = self._entries.get(key)
        if entry is None:
            raise StaleRecording((MissingTurn(booking=key[0], turn=key[1]),))
        if entry.transcript_digest != transcript_digest(transcript):
            raise StaleRecording((DigestMismatch(booking=key[0], turn=key[1]),))
        return entry.reply
