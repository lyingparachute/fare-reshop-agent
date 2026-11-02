import dataclasses
import json
import re
import stat
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from fare_reshop_agent.reshopping.cli.entry import (
    EXIT_SETUP_ERROR,
    EXIT_STALE_RECORDING,
    OutputFormat,
    emit_recorded_run,
    emit_recording_stopped,
    emit_stale_recording,
)
from fare_reshop_agent.reshopping.cli.json_output import render_json
from fare_reshop_agent.reshopping.composition.recording import (
    RecordedRun,
    re_record_command,
    record_live_review,
    record_review,
    replay_review,
)
from fare_reshop_agent.reshopping.composition.review import DataSet
from fare_reshop_agent.reshopping.composition.setup_error import SetupError
from fare_reshop_agent.reshopping.domain.exchange_rate import ExchangeRate
from fare_reshop_agent.reshopping.domain.money import Money
from fare_reshop_agent.reshopping.domain.port.reshop_source import RejectedBooking, ReshopSnapshot
from fare_reshop_agent.reshopping.domain.terms import ReviewPolicy
from fare_reshop_agent.reshopping.domain.trip import BookingRef, OfferId
from fare_reshop_agent.reshopping.infrastructure.file_problem import FileProblem
from fare_reshop_agent.reshopping.infrastructure.json_files.recording_file import (
    RecordingFile,
    RecordingFileError,
    RecordingWriteError,
    read_recording,
    recorded_turns,
    recording_text,
    write_recording,
)
from fare_reshop_agent.reshopping.infrastructure.json_fixtures.source import JsonFixtureSource
from fare_reshop_agent.reshopping.infrastructure.openai.provider_errors import (
    ProviderAuthenticationError,
)
from fare_reshop_agent.reshopping.infrastructure.openai.responses_model import OpenAIResponsesModel
from fare_reshop_agent.reshopping.orchestration.agent_model import (
    FinalText,
    ModelReply,
    Prompt,
    ProviderErrorCode,
    ProviderFailed,
    Refusal,
    ToolCallItem,
    ToolCallRequest,
    ToolCalls,
    ToolResultItem,
    ToolSpec,
    Transcript,
    Usage,
    UserMessage,
)
from fare_reshop_agent.reshopping.orchestration.agent_review import Incomplete
from fare_reshop_agent.reshopping.orchestration.booking_loop import (
    MAX_TURNS,
    IncompleteReason,
    Trace,
)
from fare_reshop_agent.reshopping.orchestration.booking_tools import tool_specs
from fare_reshop_agent.reshopping.orchestration.canonical_json import JsonValue, canonical_json
from fare_reshop_agent.reshopping.orchestration.digests import (
    digest,
    fares_feed_projection,
    money_projection,
    pnrs_projection,
    policy_projection,
    rates_projection,
    tools_projection,
    transcript_digest,
    transcript_projection,
)
from fare_reshop_agent.reshopping.orchestration.recording import (
    RecordedTurn,
    RecordedTurns,
    RecordingCompleted,
    RecordingHeader,
    RecordingModel,
    RecordingStopped,
)
from fare_reshop_agent.reshopping.orchestration.replay import (
    DigestMismatch,
    HeaderChanged,
    HeaderInput,
    LeftoverTurn,
    MissingTurn,
    RecordedModel,
    RecordedTrace,
    StaleReason,
    StaleRecording,
    changed_inputs,
    leftover_turns,
)
from fare_reshop_agent.reshopping.orchestration.review import (
    ReviewAgent,
    ReviewMode,
    ReviewReport,
    ReviewRow,
    review_with_model,
)

from cli_process import REPO_ROOT, copied_repo_data, run_cli
from openai_stub import STUB_SETTINGS, StubResponsesClient, stub_message, stub_response
from sample_data import (
    DEMO_RATES,
    EUR,
    EUR_USD,
    GBP,
    OF_1001,
    POLICY,
    REPO_FIXTURES,
    USD,
    InMemorySource,
    sample_booking,
    usd,
    with_bookings,
)
from scripted_model import RaisingModel, ScriptedModel, call, calls, rebook

PINNED_TRANSCRIPT = Transcript(
    booking_ref=BookingRef("QX7T2A"),
    turn=2,
    prompt=Prompt(data=b"Pick a fare."),
    tool_specs=(
        ToolSpec(
            name="get_booking",
            description="Read the booking.",
            parameters={"type": "object", "properties": {}, "required": []},
        ),
    ),
    items=(
        UserMessage(text="Review booking QX7T2A."),
        ToolCallItem(call_id="call_1_1", name="get_booking", arguments="{}"),
        ToolResultItem(call_id="call_1_1", result='{"ok":true}'),
    ),
)
PINNED_TRANSCRIPT_TEXT = (
    '{"booking":"QX7T2A","instructions":"Pick a fare.","items":['
    '{"kind":"user","text":"Review booking QX7T2A."},'
    '{"arguments":"{}","call_id":"call_1_1","kind":"call","name":"get_booking"},'
    '{"call_id":"call_1_1","kind":"result","result":"{\\"ok\\":true}"}],'
    '"tools":[{"description":"Read the booking.","name":"get_booking",'
    '"parameters":{"properties":{},"required":[],"type":"object"}}],"turn":2}'
)
PINNED_TRANSCRIPT_DIGEST = "114bfffd73b385f5e618c86c96332d684ca4eea723ecf4ad519bf434a5a191dd"


RECORDING_PROMPT = Prompt(data=b"Review the booking.")


def repo_snapshot() -> ReshopSnapshot:
    return JsonFixtureSource(REPO_FIXTURES).read_snapshot()


def test_canonical_json_refuses_floats() -> None:
    with pytest.raises(TypeError, match="float"):
        canonical_json({"offers": [{"price": json.loads("80.5")}]})


def test_canonical_json_ignores_key_order() -> None:
    first = canonical_json({"b": 1, "a": {"d": True, "c": None}})
    second = canonical_json({"a": {"c": None, "d": True}, "b": 1})

    assert first == second
    assert digest({"b": 1, "a": 2}) == digest({"a": 2, "b": 1})


def test_decimal_80_00_is_written_fixed_point() -> None:
    assert canonical_json(Decimal("80.00")) == "80.00"
    assert canonical_json(Decimal("80")) == "80"


def test_money_is_normalized_to_two_places() -> None:
    whole = Money(amount=Decimal("80"), currency=USD)
    cents = Money(amount=Decimal("80.00"), currency=USD)
    booking = sample_booking("QX7T2A")
    whole_fee = dataclasses.replace(booking, change_fee_per_passenger=whole)
    cents_fee = dataclasses.replace(booking, change_fee_per_passenger=cents)

    assert money_projection(whole) == {"amount": "80.00", "currency": "USD"}
    assert money_projection(whole) == money_projection(cents)
    assert digest(pnrs_projection(with_bookings(whole_fee))) == digest(
        pnrs_projection(with_bookings(cents_fee))
    )


def test_money_with_three_places_is_refused() -> None:
    with pytest.raises(ValueError, match=r"80\.005 USD"):
        money_projection(Money(amount=Decimal("80.005"), currency=USD))


def test_money_digit_change_changes_digest() -> None:
    snapshot = repo_snapshot()
    first, *others = snapshot.offers
    changed = dataclasses.replace(first, price=first.price + usd("0.01"))
    changed_snapshot = dataclasses.replace(snapshot, offers=(changed, *others))

    assert digest(fares_feed_projection(changed_snapshot)) != digest(
        fares_feed_projection(snapshot)
    )
    assert digest(pnrs_projection(changed_snapshot)) == digest(pnrs_projection(snapshot))


def test_digest_survives_field_rename() -> None:
    assert canonical_json(transcript_projection(PINNED_TRANSCRIPT)) == PINNED_TRANSCRIPT_TEXT
    assert transcript_digest(PINNED_TRANSCRIPT) == PINNED_TRANSCRIPT_DIGEST


def test_booking_and_offer_projections_pin_every_field() -> None:
    snapshot = dataclasses.replace(with_bookings(sample_booking("QX7T2A")), offers=(OF_1001,))

    assert pnrs_projection(snapshot) == {
        "bookings": [
            {
                "ref": "QX7T2A",
                "passengers": 1,
                "origin": "JFK",
                "destination": "LAX",
                "departure": "2026-08-15T08:00:00",
                "arrival": "2026-08-15T11:20:00",
                "carrier": "AA",
                "flight_number": "AA118",
                "stops": 0,
                "cabin": "ECONOMY",
                "price_per_passenger": {"amount": "480.00", "currency": "USD"},
                "total_paid": {"amount": "480.00", "currency": "USD"},
                "refundable": False,
                "change_fee_per_passenger": {"amount": "100.00", "currency": "USD"},
                "checked_bags": 1,
            }
        ],
        "rejected": [],
    }
    assert fares_feed_projection(snapshot) == {
        "capture_time": "2026-07-08T09:00:00+00:00",
        "offers": [
            {
                "offer_id": "OF-1001",
                "origin": "JFK",
                "destination": "LAX",
                "departure": "2026-08-15T08:00:00",
                "arrival": "2026-08-15T11:20:00",
                "carrier": "AA",
                "flight_number": "AA118",
                "stops": 0,
                "cabin": "ECONOMY",
                "price": {"amount": "300.00", "currency": "USD"},
                "refundable": False,
                "change_fee_per_passenger": {"amount": "100.00", "currency": "USD"},
                "checked_bags": 1,
                "seats_available": 5,
            }
        ],
    }


def field_of(entries: JsonValue, key: str) -> list[JsonValue]:
    assert isinstance(entries, list)
    values: list[JsonValue] = []
    for entry in entries:
        assert isinstance(entry, dict)
        values.append(entry[key])
    return values


def test_projections_sort_their_entries() -> None:
    late_offer = dataclasses.replace(OF_1001, offer_id=OfferId("OF-9000"))
    snapshot = dataclasses.replace(
        with_bookings(
            sample_booking("ZC3N1D"),
            RejectedBooking(ref=BookingRef("ZZ0000"), reason="bad"),
            sample_booking("HB6W9E"),
            RejectedBooking(ref=BookingRef("AA0000"), reason="bad"),
        ),
        offers=(late_offer, OF_1001),
    )
    gbp_rate = ExchangeRate(base=GBP, quote=USD, rate=Decimal("1.27"), as_of=date(2026, 7, 7))
    specs = tuple(reversed(tool_specs()))

    pnrs = pnrs_projection(snapshot)
    feed = fares_feed_projection(snapshot)
    rates = rates_projection([gbp_rate, EUR_USD])
    tools = tools_projection(specs)

    assert field_of(pnrs["bookings"], "ref") == ["HB6W9E", "ZC3N1D"]
    assert pnrs["rejected"] == ["AA0000", "ZZ0000"]
    assert field_of(feed["offers"], "offer_id") == ["OF-1001", "OF-9000"]
    assert field_of(rates, "base") == ["EUR", "GBP"]
    assert field_of(tools, "name") == ["check_offer", "get_booking", "search_offers"]


def test_policy_projection_writes_minimum_in_its_currency() -> None:
    policy = ReviewPolicy(minimum_saving=Money(amount=Decimal("43.7"), currency=EUR))

    assert policy_projection(policy) == {"minimum_saving": {"amount": "43.70", "currency": "EUR"}}


def test_rates_projection_writes_fixed_point_rate() -> None:
    rate = ExchangeRate(base=EUR, quote=USD, rate=Decimal("1E-7"), as_of=date(2026, 7, 7))

    assert rates_projection([rate]) == [
        {"as_of": "2026-07-07", "base": "EUR", "quote": "USD", "rate": "0.0000001"}
    ]


def test_transcript_digest_covers_domain_transcript() -> None:
    other_result = dataclasses.replace(
        PINNED_TRANSCRIPT,
        items=(
            *PINNED_TRANSCRIPT.items[:2],
            ToolResultItem(call_id="call_1_1", result='{"ok":false}'),
        ),
    )
    other_turn = dataclasses.replace(PINNED_TRANSCRIPT, turn=3)

    assert transcript_digest(other_result) != transcript_digest(PINNED_TRANSCRIPT)
    assert transcript_digest(other_turn) != transcript_digest(PINNED_TRANSCRIPT)


def two_eligible_bookings() -> ReshopSnapshot:
    return with_bookings(sample_booking("QX7T2A"), sample_booking("RT5K8B"))


def header_of(snapshot: ReshopSnapshot) -> RecordingHeader:
    return RecordingHeader(
        pnrs=digest(pnrs_projection(snapshot)),
        fares_feed=digest(fares_feed_projection(snapshot)),
        policy=digest(policy_projection(POLICY)),
        rates=digest(rates_projection([EUR_USD])),
        prompt=RECORDING_PROMPT.version,
        tools=digest(tools_projection(tool_specs())),
    )


def record(
    snapshot: ReshopSnapshot, scripts: dict[str, list[ModelReply]]
) -> tuple[ReviewReport, RecordingModel, ScriptedModel]:
    inner = ScriptedModel(scripts)
    wrapper = RecordingModel(inner, header_of(snapshot))
    agent = ReviewAgent(model=wrapper, prompt=RECORDING_PROMPT, mode=ReviewMode.OPENAI)
    report = review_with_model(InMemorySource(snapshot), DEMO_RATES, POLICY, agent)
    return report, wrapper, inner


def completed(wrapper: RecordingModel) -> RecordedTurns:
    outcome = wrapper.outcome()
    assert isinstance(outcome, RecordingCompleted)
    return outcome.recorded


def test_recording_keeps_every_turn() -> None:
    lookup = calls(call("get_booking"))
    scripts: dict[str, list[ModelReply]] = {
        "RT5K8B": [rebook("OF-3001")],
        "QX7T2A": [lookup, rebook("OF-1001")],
    }

    _, wrapper, inner = record(two_eligible_bookings(), scripts)

    recorded = completed(wrapper)
    turns = recorded.turns
    assert [(t.booking, t.turn, t.reply) for t in turns] == [
        ("QX7T2A", 1, lookup),
        ("QX7T2A", 2, rebook("OF-1001")),
        ("RT5K8B", 1, rebook("OF-3001")),
    ]
    assert [t.transcript_digest for t in turns] == [
        transcript_digest(shown) for shown in sorted(inner.shown, key=lambda t: t.booking_ref)
    ]
    assert recorded.model == "scripted"
    assert recorded.header == header_of(two_eligible_bookings())


def test_recording_stops_at_first_provider_failure() -> None:
    failure = ProviderFailed(code=ProviderErrorCode.TIMEOUT)
    scripts: dict[str, list[ModelReply]] = {
        "QX7T2A": [calls(call("get_booking")), failure, rebook("OF-1001")],
        "RT5K8B": [rebook("OF-3001")],
    }

    report, wrapper, inner = record(two_eligible_bookings(), scripts)

    assert wrapper.outcome() == RecordingStopped(
        booking=BookingRef("QX7T2A"), code=ProviderErrorCode.TIMEOUT
    )
    assert [(shown.booking_ref, shown.turn) for shown in inner.shown] == [
        ("QX7T2A", 1),
        ("QX7T2A", 2),
    ]
    later = next(row for row in report.results if row.outcome.ref == "RT5K8B")
    assert isinstance(later.outcome, Incomplete)
    assert later.outcome.reason is IncompleteReason.PROVIDER_ERROR


def test_mixed_reply_is_stored_with_its_text() -> None:
    mixed = calls(call("get_booking"), text="Rebook on OF-1001.")
    snapshot = with_bookings(sample_booking("QX7T2A"))

    report, wrapper, _ = record(snapshot, {"QX7T2A": [mixed]})

    (turn,) = completed(wrapper).turns
    assert isinstance(turn.reply, ToolCalls)
    assert turn.reply == mixed
    assert turn.reply.text == "Rebook on OF-1001."
    (row,) = report.results
    assert isinstance(row.outcome, Incomplete)
    assert row.outcome.reason is IncompleteReason.BAD_FINAL_ANSWER
    assert isinstance(row.trace, Trace)
    assert row.trace.tool_calls == ()


SECRET_SENTINEL = "sk-test-sentinel-0001"
RECORDING_FILE_MODE = 0o644
SIX_DIGEST_KEYS = {"pnrs", "fares_feed", "policy", "rates", "prompt", "tools"}
TOP_LEVEL_FILE_KEYS = {"schema_version", "model", "header", "turns"}
TURN_FILE_KEYS = {"booking", "turn", "transcript_digest", "reply", "usage"}


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


def test_recording_schema_round_trip() -> None:
    recorded = sample_recorded_turns()

    text = recording_text(recorded)

    assert recorded_turns(RecordingFile.model_validate(json.loads(text))) == recorded
    assert text == json.dumps(json.loads(text), sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    assert "Zürich" in text
    assert '"arguments": "{\\"offer_id\\":"' in text


def test_recording_file_is_world_readable(tmp_path: Path) -> None:
    path = tmp_path / "review-run.json"

    write_recording(path, sample_recorded_turns())

    assert stat.S_IMODE(path.stat().st_mode) == RECORDING_FILE_MODE


def test_unencodable_text_is_write_error(tmp_path: Path) -> None:
    path = tmp_path / "review-run.json"
    recorded = sample_recorded_turns()
    lone_surrogate = dataclasses.replace(
        recorded,
        turns=(
            RecordedTurn(
                booking=BookingRef("QX7T2A"),
                turn=1,
                transcript_digest="a" * 64,
                reply=FinalText(
                    text="bad \ud800 text", usage=Usage(input_tokens=1, output_tokens=1)
                ),
            ),
        ),
    )

    with pytest.raises(RecordingWriteError) as raised:
        write_recording(path, lone_surrogate)

    assert raised.value.path == path
    assert list(tmp_path.iterdir()) == []


def test_atomic_write_leaves_no_temp_file(tmp_path: Path) -> None:
    target = tmp_path / "review-run.json"
    target.mkdir()
    (target / "keep.txt").write_text("kept", encoding="utf-8")

    with pytest.raises(RecordingWriteError) as raised:
        write_recording(target, sample_recorded_turns())

    assert raised.value.path == target
    assert list(tmp_path.iterdir()) == [target]
    assert [p.name for p in target.iterdir()] == ["keep.txt"]


def test_recording_creates_missing_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)
    path = tmp_path / "recordings" / "review-run.json"
    model = ScriptedModel({"QX7T2A": [rebook("OF-1001")]})

    run = record_review(InMemorySource(with_bookings(sample_booking("QX7T2A"))), path, model)

    assert isinstance(run, RecordedRun)
    assert run.path == path
    assert path.is_file()


def test_recording_written_after_turn_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)
    path = tmp_path / "review-run.json"
    names = ["get_booking", "search_offers"] * 5
    model = ScriptedModel({"QX7T2A": [calls(call(name)) for name in names]})

    run = record_review(InMemorySource(with_bookings(sample_booking("QX7T2A"))), path, model)

    assert isinstance(run, RecordedRun)
    (row,) = run.report.results
    assert isinstance(row.outcome, Incomplete)
    assert row.outcome.reason is IncompleteReason.TURN_CAP
    document = file_document(path)
    turns = document["turns"]
    assert isinstance(turns, list)
    assert [(t["booking"], t["turn"]) for t in turns] == [("QX7T2A", n) for n in range(1, 11)]
    header = document["header"]
    assert isinstance(header, dict)
    assert set(header) == SIX_DIGEST_KEYS
    assert all(re.fullmatch("[0-9a-f]{64}", value) for value in header.values())


def test_failed_recording_keeps_old_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(REPO_ROOT)
    path = tmp_path / "review-run.json"
    path.write_bytes(b"old recording\n")
    model = ScriptedModel({"QX7T2A": [ProviderFailed(code=ProviderErrorCode.RATE_LIMIT)]})

    stopped = record_review(InMemorySource(with_bookings(sample_booking("QX7T2A"))), path, model)

    assert stopped == RecordingStopped(
        booking=BookingRef("QX7T2A"), code=ProviderErrorCode.RATE_LIMIT
    )
    assert path.read_bytes() == b"old recording\n"
    assert list(tmp_path.iterdir()) == [path]
    assert emit_recording_stopped(stopped, DataSet.SAMPLE) == EXIT_SETUP_ERROR
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines() == [
        "error: booking QX7T2A: recording stopped",
        "reason: rate_limit",
        "fix: uv run --env-file .env.local --extra live fare-reshop review --data sample"
        " --model openai --record",
    ]


def test_recording_has_no_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(REPO_ROOT)
    answer = canonical_json(
        {
            "decision": "rebook",
            "offer_id": "OF-1001",
            "reasoning": "Same flight, lower fare.",
            "confidence": Decimal("0.9"),
        }
    )
    message = stub_message({"type": "output_text", "text": answer, "annotations": []})
    message["id"] = f"msg_{SECRET_SENTINEL}"
    response = stub_response([message], response_id=f"resp_{SECRET_SENTINEL}")
    model = OpenAIResponsesModel(
        client=StubResponsesClient(outcome=response), settings=STUB_SETTINGS
    )
    path = tmp_path / "review-run.json"

    run = record_review(InMemorySource(with_bookings(sample_booking("QX7T2A"))), path, model)

    assert isinstance(run, RecordedRun)
    assert emit_recorded_run(run, OutputFormat.JSON) == 0
    captured = capsys.readouterr()
    assert SECRET_SENTINEL not in path.read_text(encoding="utf-8")
    assert SECRET_SENTINEL not in captured.out
    assert SECRET_SENTINEL not in captured.err
    assert captured.err == f"recording written to {path}\n"
    document = file_document(path)
    assert set(document) == TOP_LEVEL_FILE_KEYS
    turns = document["turns"]
    assert isinstance(turns, list)
    assert all(set(turn) == TURN_FILE_KEYS for turn in turns)


def test_record_flag_needs_openai_exits_2() -> None:
    result = run_cli("review", "--model", "none", "--record")

    assert result.returncode == EXIT_SETUP_ERROR
    assert result.stdout == ""
    assert "record needs --model openai" in result.stderr


SAMPLE_REPLIES: dict[str, list[ModelReply]] = {
    "QX7T2A": [calls(call("get_booking")), rebook("OF-1001")],
    "RT5K8B": [rebook("OF-3001")],
}
RE_RECORD_SAMPLE = (
    "fix: uv run --env-file .env.local --extra live fare-reshop review --data sample"
    " --model openai --record"
)


def recorded_run(
    folder: Path, snapshot: ReshopSnapshot, scripts: dict[str, list[ModelReply]]
) -> RecordedRun:
    path = folder / "recordings" / "review-run.json"
    run = record_review(InMemorySource(snapshot), path, ScriptedModel(scripts))
    assert isinstance(run, RecordedRun)
    return run


def assert_replay_matches(recorded: ReviewRow, replayed: ReviewRow) -> None:
    assert isinstance(recorded.trace, Trace)
    assert isinstance(replayed.trace, RecordedTrace)
    assert (replayed.outcome, replayed.trace.trace) == (recorded.outcome, recorded.trace)


def stale_reasons(snapshot: ReshopSnapshot, path: Path) -> tuple[StaleReason, ...]:
    with pytest.raises(StaleRecording) as raised:
        replay_review(InMemorySource(snapshot), path)
    return raised.value.reasons


def edited_copy(path: Path, edit: Callable[[RecordedTurns], RecordedTurns]) -> Path:
    write_recording(path, edit(read_recording(path)))
    return path


def lower_policy(folder: Path) -> None:
    policy = folder / "config" / "policy.toml"
    text = policy.read_text(encoding="utf-8").replace('amount = "50.00"', 'amount = "40.00"')
    policy.write_text(text, encoding="utf-8")


def test_changed_fixture_is_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)
    snapshot = two_eligible_bookings()
    path = recorded_run(tmp_path, snapshot, SAMPLE_REPLIES).path
    first, *others = snapshot.offers
    changed = dataclasses.replace(
        snapshot, offers=(dataclasses.replace(first, price=first.price + usd("1.00")), *others)
    )

    assert stale_reasons(changed, path) == (HeaderChanged(input=HeaderInput.FARES_FEED),)


def test_stale_header_names_changed_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(copied_repo_data(tmp_path))
    snapshot = two_eligible_bookings()
    path = recorded_run(tmp_path, snapshot, SAMPLE_REPLIES).path
    lower_policy(tmp_path)

    assert stale_reasons(snapshot, path) == (HeaderChanged(input=HeaderInput.POLICY),)


def test_unknown_schema_version_is_read_error(tmp_path: Path) -> None:
    path = tmp_path / "review-run.json"
    document = json.loads(recording_text(sample_recorded_turns()))
    document["schema_version"] = 2
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RecordingFileError, match="schema_version is 2") as raised:
        read_recording(path)

    assert raised.value.path == path


def test_missing_file_is_read_error(tmp_path: Path) -> None:
    path = tmp_path / "recordings" / "review-run.json"

    with pytest.raises(RecordingFileError) as raised:
        read_recording(path)

    assert raised.value.path == path
    assert raised.value.problem is FileProblem.MISSING


def test_unreadable_file_is_read_error(tmp_path: Path) -> None:
    path = tmp_path / "review-run.json"
    path.write_text('{"schema_version": 1,', encoding="utf-8")

    with pytest.raises(RecordingFileError) as raised:
        read_recording(path)

    assert raised.value.path == path
    assert raised.value.problem is FileProblem.MALFORMED


def test_replay_reproduces_turn_cap_booking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(REPO_ROOT)
    snapshot = with_bookings(sample_booking("QX7T2A"))
    names = ["get_booking", "search_offers"] * 5
    path = recorded_run(tmp_path, snapshot, {"QX7T2A": [calls(call(name)) for name in names]}).path

    (row,) = replay_review(InMemorySource(snapshot), path).results

    assert isinstance(row.outcome, Incomplete)
    assert row.outcome.reason is IncompleteReason.TURN_CAP
    assert isinstance(row.trace, RecordedTrace)
    assert row.trace.trace.turns == MAX_TURNS


def test_replay_trace_shows_recorded_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)
    snapshot = two_eligible_bookings()
    path = recorded_run(tmp_path, snapshot, SAMPLE_REPLIES).path

    report = replay_review(InMemorySource(snapshot), path)

    document = json.loads(render_json(report))
    assert document["mode"] == "recorded"
    traces = {result["pnr"]: result["trace"] for result in document["results"]}
    assert list(traces["QX7T2A"]) == [
        "prompt_version",
        "turns",
        "recorded_model",
        "recorded_usage",
        "tool_calls",
        "provider_error_code",
    ]
    assert traces["QX7T2A"]["recorded_model"] == "scripted"
    assert traces["QX7T2A"]["recorded_usage"] == {"input_tokens": 200, "output_tokens": 40}
    assert traces["RT5K8B"]["recorded_usage"] == {"input_tokens": 100, "output_tokens": 20}


def test_changed_turn_is_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)
    snapshot = two_eligible_bookings()
    path = edited_copy(
        recorded_run(tmp_path, snapshot, SAMPLE_REPLIES).path,
        lambda recorded: dataclasses.replace(
            recorded,
            turns=tuple(
                dataclasses.replace(turn, transcript_digest="0" * 64)
                if (turn.booking, turn.turn) == ("QX7T2A", 2)
                else turn
                for turn in recorded.turns
            ),
        ),
    )

    assert stale_reasons(snapshot, path) == (DigestMismatch(booking=BookingRef("QX7T2A"), turn=2),)


def test_missing_turn_is_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)
    snapshot = two_eligible_bookings()
    path = edited_copy(
        recorded_run(tmp_path, snapshot, SAMPLE_REPLIES).path,
        lambda recorded: dataclasses.replace(
            recorded,
            turns=tuple(t for t in recorded.turns if (t.booking, t.turn) != ("QX7T2A", 2)),
        ),
    )

    assert stale_reasons(snapshot, path) == (MissingTurn(booking=BookingRef("QX7T2A"), turn=2),)


def test_mixed_reply_record_and_replay_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(REPO_ROOT)
    snapshot = with_bookings(sample_booking("QX7T2A"))
    mixed = calls(call("get_booking"), text="Rebook on OF-1001.")
    run = recorded_run(tmp_path, snapshot, {"QX7T2A": [mixed]})

    (row,) = replay_review(InMemorySource(snapshot), run.path).results

    turns = file_document(run.path)["turns"]
    assert isinstance(turns, list)
    assert turns[0]["reply"] == {
        "kind": "tool_calls",
        "text": "Rebook on OF-1001.",
        "calls": [{"name": "get_booking", "arguments": "{}"}],
    }
    assert isinstance(row.outcome, Incomplete)
    assert row.outcome.reason is IncompleteReason.BAD_FINAL_ANSWER
    assert isinstance(row.trace, RecordedTrace)
    assert row.trace.trace.tool_calls == ()
    assert_replay_matches(run.report.results[0], row)


def test_malformed_arguments_replay_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(REPO_ROOT)
    snapshot = with_bookings(sample_booking("QX7T2A"))
    replies: list[ModelReply] = [calls(call("check_offer", '{"offer_id":')), rebook("OF-1001")]
    run = recorded_run(tmp_path, snapshot, {"QX7T2A": replies})

    (row,) = replay_review(InMemorySource(snapshot), run.path).results

    assert isinstance(row.trace, RecordedTrace)
    (traced,) = row.trace.trace.tool_calls
    assert (traced.name, traced.arguments, traced.ok) == ("check_offer", '{"offer_id":', False)
    assert_replay_matches(run.report.results[0], row)


def test_stale_recording_passes_through_the_loop() -> None:
    empty = RecordedTurns(header=header_of(two_eligible_bookings()), model="scripted", turns=())
    agent = ReviewAgent(
        model=RecordedModel(empty), prompt=RECORDING_PROMPT, mode=ReviewMode.RECORDED
    )

    with pytest.raises(StaleRecording) as raised:
        review_with_model(InMemorySource(two_eligible_bookings()), DEMO_RATES, POLICY, agent)

    assert raised.value.reasons == (MissingTurn(booking=BookingRef("QX7T2A"), turn=1),)


def test_stale_recording_exits_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(copied_repo_data(tmp_path))
    source = JsonFixtureSource(tmp_path / "fixtures")
    path = tmp_path / "recordings" / "review-run.json"
    assert isinstance(record_review(source, path, ScriptedModel(SAMPLE_REPLIES)), RecordedRun)
    lower_policy(tmp_path)

    result = run_cli("review", "--model", "recorded", cwd=tmp_path)

    assert result.returncode == EXIT_STALE_RECORDING
    assert result.stdout == ""
    lines = result.stderr.splitlines()
    assert lines[0] == "error: stale recording: policy changed"
    assert lines[2] == RE_RECORD_SAMPLE


def test_record_write_failure_is_setup_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(REPO_ROOT)
    path = tmp_path / "review-run.json"
    path.mkdir()
    model = ScriptedModel({"QX7T2A": [rebook("OF-1001")]})

    with pytest.raises(SetupError) as raised:
        record_review(InMemorySource(with_bookings(sample_booking("QX7T2A"))), path, model)

    assert raised.value.error == f"cannot write the recording {path}"
    assert raised.value.fix == f"make {tmp_path} a writable folder, then record again"


def test_live_record_maps_provider_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)

    with pytest.raises(SetupError) as raised:
        record_live_review(
            DataSet.SAMPLE, {}, model_factory=lambda _: RaisingModel(ProviderAuthenticationError())
        )

    assert raised.value.error == "OpenAI rejected the API key"


@pytest.mark.parametrize("changed", list(HeaderInput))
def test_changed_inputs_names_each_header_input(changed: HeaderInput) -> None:
    recorded = header_of(two_eligible_bookings())
    current = dataclasses.replace(recorded, **{changed.value: "0" * 64})

    assert changed_inputs(current, recorded) == (changed,)


def test_duplicate_turn_is_read_error(tmp_path: Path) -> None:
    path = tmp_path / "review-run.json"
    document = json.loads(recording_text(sample_recorded_turns()))
    document["turns"].append(document["turns"][0])
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(
        RecordingFileError, match="booking QX7T2A turn 1 is recorded more than once"
    ):
        read_recording(path)


SAMPLE_FIX_NONE = "fix: uv run fare-reshop review --data sample --model none"


def test_leftover_turn_is_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)
    snapshot = two_eligible_bookings()
    run = recorded_run(tmp_path, snapshot, SAMPLE_REPLIES)
    recorded = read_recording(run.path)
    (last,) = (t for t in recorded.turns if (t.booking, t.turn) == ("RT5K8B", 1))
    extra = dataclasses.replace(last, turn=2)
    write_recording(run.path, dataclasses.replace(recorded, turns=(*recorded.turns, extra)))

    assert stale_reasons(snapshot, run.path) == (
        LeftoverTurn(booking=BookingRef("RT5K8B"), turn=2),
    )


def test_missing_recording_exits_2(tmp_path: Path) -> None:
    copied_repo_data(tmp_path)

    result = run_cli("review", "--model", "recorded", cwd=tmp_path)

    assert result.returncode == EXIT_SETUP_ERROR
    assert result.stdout == ""
    assert result.stderr.splitlines() == [
        "error: no recording at recordings/review-run.json",
        "reason: the recorded run replays that committed file, and this checkout does not have it",
        SAMPLE_FIX_NONE,
    ]


def test_missing_scenario_recording_names_its_path(tmp_path: Path) -> None:
    copied_repo_data(tmp_path)

    result = run_cli("review", "--data", "scenarios", "--model", "recorded", cwd=tmp_path)

    assert result.returncode == EXIT_SETUP_ERROR
    lines = result.stderr.splitlines()
    assert lines[0] == "error: no recording at recordings/scenarios-run.json"
    assert lines[2] == "fix: uv run fare-reshop review --data scenarios --model none"


def test_unreadable_recording_exits_2(tmp_path: Path) -> None:
    copied_repo_data(tmp_path)
    (tmp_path / "recordings").mkdir()
    (tmp_path / "recordings" / "review-run.json").write_text("{not json", encoding="utf-8")

    result = run_cli("review", "--model", "recorded", cwd=tmp_path)

    assert result.returncode == EXIT_SETUP_ERROR
    assert result.stdout == ""
    error, reason, fix = result.stderr.splitlines()
    assert error == "error: the recording recordings/review-run.json cannot be read"
    assert reason.startswith("reason: ")
    assert fix == SAMPLE_FIX_NONE


@pytest.mark.parametrize(
    ("data_set", "command"),
    [
        (
            DataSet.SAMPLE,
            "uv run --env-file .env.local --extra live fare-reshop review"
            " --data sample --model openai --record",
        ),
        (
            DataSet.SCENARIOS,
            "uv run --env-file .env.local --extra live fare-reshop review"
            " --data scenarios --model openai --record",
        ),
    ],
)
def test_re_record_command_per_data_set(data_set: DataSet, command: str) -> None:
    assert re_record_command(data_set) == command


def test_stale_message_names_every_reason(capsys: pytest.CaptureFixture[str]) -> None:
    reasons: tuple[StaleReason, ...] = (
        HeaderChanged(input=HeaderInput.TOOLS),
        DigestMismatch(booking=BookingRef("QX7T2A"), turn=2),
        MissingTurn(booking=BookingRef("QX7T2A"), turn=3),
        LeftoverTurn(booking=BookingRef("RT5K8B"), turn=2),
    )

    exit_code = emit_stale_recording(StaleRecording(reasons), DataSet.SCENARIOS)

    assert exit_code == EXIT_STALE_RECORDING
    lines = capsys.readouterr().err.splitlines()
    assert lines[0] == (
        "error: stale recording: tools changed;"
        " booking QX7T2A turn 2 saw a different transcript;"
        " booking QX7T2A turn 3 is missing;"
        " booking RT5K8B turn 2 was recorded but never asked for"
    )
    assert lines[2] == (
        "fix: uv run --env-file .env.local --extra live fare-reshop review"
        " --data scenarios --model openai --record"
    )


def test_booking_without_model_turns_leaves_every_turn_over() -> None:
    recorded = sample_recorded_turns()
    shuffled = dataclasses.replace(recorded, turns=tuple(reversed(recorded.turns)))

    assert leftover_turns(shuffled, {BookingRef("QX7T2A"): 1}) == (
        LeftoverTurn(booking=BookingRef("QX7T2A"), turn=2),
        LeftoverTurn(booking=BookingRef("RT5K8B"), turn=1),
    )
