import json
from pathlib import Path

from fare_reshop_agent.reshopping.domain.port.reshop_source import ReshopSnapshot
from fare_reshop_agent.reshopping.domain.trip import BookingRef
from fare_reshop_agent.reshopping.orchestration.agent_model import (
    FinalText,
    Prompt,
    Refusal,
    ToolCallRequest,
    ToolCalls,
    Usage,
)
from fare_reshop_agent.reshopping.orchestration.recording import (
    RecordedTurn,
    RecordedTurns,
    RecordingHeader,
    compute_header,
)

from sample_data import (
    EUR_USD,
    POLICY,
    sample_booking,
    with_bookings,
)

RECORDING_PROMPT = Prompt(data=b"Review the booking.")


def two_eligible_bookings() -> ReshopSnapshot:
    return with_bookings(sample_booking("QX7T2A"), sample_booking("RT5K8B"))


def header_of(snapshot: ReshopSnapshot) -> RecordingHeader:
    return compute_header(snapshot, (EUR_USD,), POLICY, RECORDING_PROMPT)


def sample_recorded_turns() -> RecordedTurns:
    usage = Usage(input_tokens=120, output_tokens=30)
    return RecordedTurns(
        header=header_of(two_eligible_bookings()),
        model="gpt-test",
        turns=(
            RecordedTurn(
                booking=BookingRef("QX7T2A"),
                turn=1,
                transcript_digest="a" * 64,
                reply=ToolCalls(
                    calls=(ToolCallRequest(name="check_offer", arguments='{"offer_id":'),),
                    text=None,
                    usage=usage,
                ),
            ),
            RecordedTurn(
                booking=BookingRef("QX7T2A"),
                turn=2,
                transcript_digest="b" * 64,
                reply=FinalText(text="Rebook to Zürich? No: OF-1001.", usage=usage),
            ),
            RecordedTurn(
                booking=BookingRef("RT5K8B"),
                turn=1,
                transcript_digest="c" * 64,
                reply=Refusal(text="I cannot help.", usage=usage),
            ),
        ),
    )


def file_document(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document
