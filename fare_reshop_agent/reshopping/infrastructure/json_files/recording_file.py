import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Annotated, Literal, assert_never

from pydantic import Field, StrictInt, StrictStr

from fare_reshop_agent.reshopping.domain.trip import BookingRef
from fare_reshop_agent.reshopping.infrastructure.file_problem import (
    FileProblem,
    FileReadError,
    StrictRecord,
    read_model,
)
from fare_reshop_agent.reshopping.orchestration.agent_model import (
    FinalText,
    Refusal,
    ToolCallRequest,
    ToolCalls,
    Usage,
)
from fare_reshop_agent.reshopping.orchestration.recording import (
    RecordedReply,
    RecordedTurn,
    RecordedTurns,
    RecordingHeader,
)

SCHEMA_VERSION = 1
FILE_ENCODING = "utf-8"
INDENT = 2
TEMP_SUFFIX = ".tmp"
FILE_MODE = 0o644


class RecordingFileError(FileReadError):
    pass


class RecordingWriteError(Exception):
    def __init__(self, *, path: Path, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


class _UsageRecord(StrictRecord):
    input_tokens: StrictInt
    output_tokens: StrictInt


class _CallRecord(StrictRecord):
    name: StrictStr
    arguments: StrictStr


class _ToolCallsRecord(StrictRecord):
    kind: Literal["tool_calls"]
    text: StrictStr | None
    calls: tuple[_CallRecord, ...] = Field(min_length=1)


class _FinalRecord(StrictRecord):
    kind: Literal["final"]
    text: StrictStr


class _RefusalRecord(StrictRecord):
    kind: Literal["refusal"]
    text: StrictStr


type _ReplyRecord = Annotated[
    _ToolCallsRecord | _FinalRecord | _RefusalRecord, Field(discriminator="kind")
]


class _TurnRecord(StrictRecord):
    booking: StrictStr
    turn: StrictInt
    transcript_digest: StrictStr
    reply: _ReplyRecord
    usage: _UsageRecord


class _HeaderRecord(StrictRecord):
    pnrs: StrictStr
    fares_feed: StrictStr
    policy: StrictStr
    rates: StrictStr
    prompt: StrictStr
    tools: StrictStr


class RecordingFile(StrictRecord):
    schema_version: StrictInt
    model: StrictStr
    header: _HeaderRecord
    turns: tuple[_TurnRecord, ...]


def recording_text(recorded: RecordedTurns) -> str:
    document = RecordingFile(
        schema_version=SCHEMA_VERSION,
        model=recorded.model,
        header=_HeaderRecord(
            pnrs=recorded.header.pnrs,
            fares_feed=recorded.header.fares_feed,
            policy=recorded.header.policy,
            rates=recorded.header.rates,
            prompt=recorded.header.prompt,
            tools=recorded.header.tools,
        ),
        turns=tuple(_turn_record(turn) for turn in recorded.turns),
    )
    payload = document.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, indent=INDENT, ensure_ascii=False) + "\n"


def recorded_turns(document: RecordingFile) -> RecordedTurns:
    header = document.header
    return RecordedTurns(
        header=RecordingHeader(
            pnrs=header.pnrs,
            fares_feed=header.fares_feed,
            policy=header.policy,
            rates=header.rates,
            prompt=header.prompt,
            tools=header.tools,
        ),
        model=document.model,
        turns=tuple(_recorded_turn(turn) for turn in document.turns),
    )


def read_recording(path: Path) -> RecordedTurns:
    document = read_model(path, RecordingFile, RecordingFileError, json.loads, json.JSONDecodeError)
    if document.schema_version != SCHEMA_VERSION:
        raise RecordingFileError(
            path=path,
            problem=FileProblem.MALFORMED,
            fact=f"schema_version is {document.schema_version}, and only {SCHEMA_VERSION} is known",
        )
    counts = Counter((turn.booking, turn.turn) for turn in document.turns)
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    if duplicates:
        booking, turn = duplicates[0]
        raise RecordingFileError(
            path=path,
            problem=FileProblem.MALFORMED,
            fact=f"booking {booking} turn {turn} is recorded more than once",
        )
    return recorded_turns(document)


def write_recording(path: Path, recorded: RecordedTurns) -> None:
    try:
        data = recording_text(recorded).encode(FILE_ENCODING)
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=TEMP_SUFFIX
        )
    except (OSError, UnicodeEncodeError) as err:
        raise RecordingWriteError(path=path, reason=str(err)) from err
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as temp_file:
            temp_file.write(data)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        temp_path.chmod(FILE_MODE)
        temp_path.replace(path)
    except OSError as err:
        raise RecordingWriteError(path=path, reason=str(err)) from err
    finally:
        temp_path.unlink(missing_ok=True)


def _turn_record(turn: RecordedTurn) -> _TurnRecord:
    usage = turn.reply.usage
    return _TurnRecord(
        booking=turn.booking,
        turn=turn.turn,
        transcript_digest=turn.transcript_digest,
        reply=_reply_record(turn.reply),
        usage=_UsageRecord(input_tokens=usage.input_tokens, output_tokens=usage.output_tokens),
    )


def _reply_record(reply: RecordedReply) -> _ToolCallsRecord | _FinalRecord | _RefusalRecord:
    match reply:
        case ToolCalls():
            calls = tuple(_CallRecord(name=c.name, arguments=c.arguments) for c in reply.calls)
            return _ToolCallsRecord(kind="tool_calls", text=reply.text, calls=calls)
        case FinalText():
            return _FinalRecord(kind="final", text=reply.text)
        case Refusal():
            return _RefusalRecord(kind="refusal", text=reply.text)
        case _:
            assert_never(reply)


def _recorded_turn(record: _TurnRecord) -> RecordedTurn:
    return RecordedTurn(
        booking=BookingRef(record.booking),
        turn=record.turn,
        transcript_digest=record.transcript_digest,
        reply=_reply(record.reply, record.usage),
    )


def _reply(
    record: _ToolCallsRecord | _FinalRecord | _RefusalRecord, usage_record: _UsageRecord
) -> RecordedReply:
    usage = Usage(input_tokens=usage_record.input_tokens, output_tokens=usage_record.output_tokens)
    match record:
        case _ToolCallsRecord():
            calls = tuple(ToolCallRequest(name=c.name, arguments=c.arguments) for c in record.calls)
            return ToolCalls(calls=calls, text=record.text, usage=usage)
        case _FinalRecord():
            return FinalText(text=record.text, usage=usage)
        case _RefusalRecord():
            return Refusal(text=record.text, usage=usage)
        case _:
            assert_never(record)
