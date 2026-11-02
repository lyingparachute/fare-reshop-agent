import dataclasses
from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never

from fare_reshop_agent.reshopping.orchestration.agent_model import (
    NO_USAGE,
    AgentModel,
    FinalText,
    Prompt,
    ProviderErrorCode,
    ProviderFailed,
    Refusal,
    ToolCallItem,
    ToolCallRequest,
    ToolCalls,
    ToolResultItem,
    Transcript,
    TranscriptItem,
    Usage,
    UserMessage,
)
from fare_reshop_agent.reshopping.orchestration.booking_tools import BookingTools, tool_specs
from fare_reshop_agent.reshopping.orchestration.final_answer import FinalAnswer, parse_final_answer
from fare_reshop_agent.reshopping.orchestration.model_json import Malformed, canonical_arguments

MAX_TURNS = 10


class IncompleteReason(StrEnum):
    TURN_CAP = "turn_cap"
    REPEATED_CALL = "repeated_call"
    BAD_FINAL_ANSWER = "bad_final_answer"
    REFUSAL = "refusal"
    PROVIDER_ERROR = "provider_error"


@dataclass(frozen=True, slots=True, kw_only=True)
class TracedCall:
    name: str
    arguments: str
    ok: bool

    def is_same_call(self, name: str, arguments: str) -> bool:
        return (self.name, self.arguments) == (name, arguments)


@dataclass(frozen=True, slots=True, kw_only=True)
class Trace:
    prompt_version: str
    turns: int
    usage: Usage
    tool_calls: tuple[TracedCall, ...]
    provider_error_code: ProviderErrorCode | None

    @classmethod
    def empty(cls, prompt: Prompt) -> "Trace":
        return cls(
            prompt_version=prompt.version,
            turns=0,
            usage=NO_USAGE,
            tool_calls=(),
            provider_error_code=None,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Answered:
    answer: FinalAnswer


@dataclass(frozen=True, slots=True, kw_only=True)
class Stopped:
    reason: IncompleteReason


@dataclass(frozen=True, slots=True, kw_only=True)
class LoopRun:
    end: Answered | Stopped
    trace: Trace


def run_booking_loop(tools: BookingTools, model: AgentModel, prompt: Prompt) -> LoopRun:
    ref = tools.terms.booking.ref
    transcript = Transcript(
        booking_ref=ref,
        turn=1,
        prompt=prompt,
        tool_specs=tool_specs(),
        items=(UserMessage(text=f"Review booking {ref}."),),
    )
    trace = Trace.empty(prompt)
    while True:
        reply = model.next_step(transcript)
        usage = NO_USAGE if isinstance(reply, ProviderFailed) else reply.usage
        trace = dataclasses.replace(trace, turns=trace.turns + 1, usage=trace.usage + usage)
        match reply:
            case ToolCalls():
                if reply.text is not None:
                    return LoopRun(
                        end=Stopped(reason=IncompleteReason.BAD_FINAL_ANSWER), trace=trace
                    )
                if transcript.turn == MAX_TURNS:
                    return LoopRun(end=Stopped(reason=IncompleteReason.TURN_CAP), trace=trace)
                ran = _run_calls(tools, transcript, trace, reply.calls)
                if isinstance(ran, LoopRun):
                    return ran
                transcript, trace = ran
            case FinalText():
                return LoopRun(end=_final_end(reply.text), trace=trace)
            case Refusal():
                return LoopRun(end=Stopped(reason=IncompleteReason.REFUSAL), trace=trace)
            case ProviderFailed():
                trace = dataclasses.replace(trace, provider_error_code=reply.code)
                return LoopRun(end=Stopped(reason=IncompleteReason.PROVIDER_ERROR), trace=trace)
            case _:
                assert_never(reply)


def _final_end(text: str) -> Answered | Stopped:
    answer = parse_final_answer(text)
    if isinstance(answer, Malformed):
        return Stopped(reason=IncompleteReason.BAD_FINAL_ANSWER)
    return Answered(answer=answer)


def _run_calls(
    tools: BookingTools, transcript: Transcript, trace: Trace, calls: tuple[ToolCallRequest, ...]
) -> tuple[Transcript, Trace] | LoopRun:
    items: list[TranscriptItem] = []
    for position, call in enumerate(calls, start=1):
        arguments = canonical_arguments(call)
        if trace.tool_calls and trace.tool_calls[-1].is_same_call(call.name, arguments):
            return LoopRun(end=Stopped(reason=IncompleteReason.REPEATED_CALL), trace=trace)
        call_id = f"call_{transcript.turn}_{position}"
        result = tools.run(call)
        items += [
            ToolCallItem(call_id=call_id, name=call.name, arguments=call.arguments),
            ToolResultItem(call_id=call_id, result=result.text),
        ]
        traced = TracedCall(name=call.name, arguments=arguments, ok=result.ok)
        trace = dataclasses.replace(trace, tool_calls=(*trace.tool_calls, traced))
    next_transcript = dataclasses.replace(
        transcript, turn=transcript.turn + 1, items=transcript.items + tuple(items)
    )
    return next_transcript, trace
