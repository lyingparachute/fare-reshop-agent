from dataclasses import dataclass
from typing import assert_never

from fare_reshop_agent.reshopping.domain.trip import BookingRef
from fare_reshop_agent.reshopping.orchestration.agent_model import (
    AgentModel,
    FinalText,
    ModelReply,
    ProviderErrorCode,
    ProviderFailed,
    Refusal,
    ToolCalls,
    Transcript,
)
from fare_reshop_agent.reshopping.orchestration.digests import transcript_digest

type RecordedReply = ToolCalls | FinalText | Refusal


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordingHeader:
    pnrs: str
    fares_feed: str
    policy: str
    rates: str
    prompt: str
    tools: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordedTurn:
    booking: BookingRef
    turn: int
    transcript_digest: str
    reply: RecordedReply


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordedTurns:
    header: RecordingHeader
    model: str
    turns: tuple[RecordedTurn, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordingCompleted:
    recorded: RecordedTurns


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordingStopped:
    booking: BookingRef
    code: ProviderErrorCode


class RecordingModel:
    def __init__(self, inner: AgentModel, header: RecordingHeader) -> None:
        self._inner = inner
        self._header = header
        self._turns: list[RecordedTurn] = []
        self._stop: RecordingStopped | None = None

    @property
    def model_name(self) -> str:
        return self._inner.model_name

    def next_step(self, transcript: Transcript) -> ModelReply:
        if self._stop is not None:
            return ProviderFailed(code=self._stop.code)
        reply = self._inner.next_step(transcript)
        match reply:
            case ProviderFailed():
                self._stop = RecordingStopped(booking=transcript.booking_ref, code=reply.code)
            case ToolCalls() | FinalText() | Refusal():
                self._turns.append(
                    RecordedTurn(
                        booking=transcript.booking_ref,
                        turn=transcript.turn,
                        transcript_digest=transcript_digest(transcript),
                        reply=reply,
                    )
                )
            case _:
                assert_never(reply)
        return reply

    def outcome(self) -> RecordingCompleted | RecordingStopped:
        if self._stop is not None:
            return self._stop
        turns = sorted(self._turns, key=lambda turn: (turn.booking, turn.turn))
        return RecordingCompleted(
            recorded=RecordedTurns(header=self._header, model=self.model_name, turns=tuple(turns))
        )
