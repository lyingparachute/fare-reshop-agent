import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from fare_reshop_agent.reshopping.domain.trip import BookingRef
from fare_reshop_agent.reshopping.orchestration.canonical_json import JsonValue

PROMPT_ENCODING = "utf-8"


@dataclass(frozen=True, slots=True, kw_only=True)
class Prompt:
    data: bytes

    @property
    def text(self) -> str:
        return self.data.decode(PROMPT_ENCODING)

    @property
    def version(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, JsonValue]


@dataclass(frozen=True, slots=True, kw_only=True)
class Usage:
    input_tokens: int
    output_tokens: int

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


NO_USAGE = Usage(input_tokens=0, output_tokens=0)


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCallRequest:
    name: str
    arguments: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCalls:
    calls: tuple[ToolCallRequest, ...]
    text: str | None
    usage: Usage

    def __post_init__(self) -> None:
        if not self.calls:
            raise ValueError("a tool-calls reply needs at least one call")


@dataclass(frozen=True, slots=True, kw_only=True)
class FinalText:
    text: str
    usage: Usage


@dataclass(frozen=True, slots=True, kw_only=True)
class Refusal:
    text: str
    usage: Usage


class ProviderErrorCode(StrEnum):
    CONNECTION = "connection"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderFailed:
    code: ProviderErrorCode


type ModelReply = ToolCalls | FinalText | Refusal | ProviderFailed


@dataclass(frozen=True, slots=True, kw_only=True)
class UserMessage:
    text: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCallItem:
    call_id: str
    name: str
    arguments: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolResultItem:
    call_id: str
    result: str


type TranscriptItem = UserMessage | ToolCallItem | ToolResultItem


@dataclass(frozen=True, slots=True, kw_only=True)
class Transcript:
    booking_ref: BookingRef
    turn: int
    prompt: Prompt
    tool_specs: tuple[ToolSpec, ...]
    items: tuple[TranscriptItem, ...]


class AgentModel(Protocol):
    @property
    def model_name(self) -> str: ...

    def next_step(self, transcript: Transcript) -> ModelReply: ...
