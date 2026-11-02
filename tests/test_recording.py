import dataclasses
import json
import os
import re
import stat
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from fare_reshop_agent.reshopping.cli.entry import (
    EXIT_SETUP_ERROR,
    OutputFormat,
    emit_recorded_run,
    emit_recording_stopped,
)
from fare_reshop_agent.reshopping.composition.recording import (
    RecordedRun,
    record_live_review,
    record_review,
)
from fare_reshop_agent.reshopping.composition.review import (
    DataSet,
)
from fare_reshop_agent.reshopping.composition.setup_error import SetupError
from fare_reshop_agent.reshopping.domain.port.reshop_source import ReshopSnapshot
from fare_reshop_agent.reshopping.domain.trip import BookingRef
from fare_reshop_agent.reshopping.infrastructure.json_files.recording_file import (
    RecordingFile,
    RecordingWriteError,
    recorded_turns,
    recording_text,
    write_recording,
)
from fare_reshop_agent.reshopping.infrastructure.openai.provider_errors import (
    ProviderAuthenticationError,
)
from fare_reshop_agent.reshopping.infrastructure.openai.responses_model import OpenAIResponsesModel
from fare_reshop_agent.reshopping.orchestration.agent_model import (
    FinalText,
    ModelReply,
    ProviderErrorCode,
    ProviderFailed,
    ToolCalls,
    Usage,
)
from fare_reshop_agent.reshopping.orchestration.agent_review import Incomplete
from fare_reshop_agent.reshopping.orchestration.booking_loop import (
    IncompleteReason,
    Trace,
)
from fare_reshop_agent.reshopping.orchestration.canonical_json import canonical_json
from fare_reshop_agent.reshopping.orchestration.digests import (
    transcript_digest,
)
from fare_reshop_agent.reshopping.orchestration.recording import (
    RecordedTurn,
    RecordedTurns,
    RecordingCompleted,
    RecordingModel,
    RecordingStopped,
)
from fare_reshop_agent.reshopping.orchestration.review import (
    ReviewAgent,
    ReviewMode,
    ReviewReport,
    review_with_model,
)

from cli_process import REPO_ROOT, run_cli
from openai_stub import STUB_SETTINGS, StubResponsesClient, stub_message, stub_response
from recording_data import (
    RECORDING_PROMPT,
    file_document,
    header_of,
    sample_recorded_turns,
    two_eligible_bookings,
)
from sample_data import (
    DEMO_RATES,
    POLICY,
    InMemorySource,
    sample_booking,
    with_bookings,
)
from scripted_model import RaisingModel, ScriptedModel, call, calls, rebook

SECRET_SENTINEL = "sk-test-sentinel-0001"
RECORDING_FILE_MODE = 0o644
SIX_DIGEST_KEYS = {"pnrs", "fares_feed", "policy", "rates", "prompt", "tools"}
TOP_LEVEL_FILE_KEYS = {"schema_version", "model", "header", "turns"}
TURN_FILE_KEYS = {"booking", "turn", "transcript_digest", "reply", "usage"}
COST_SCRIPT = REPO_ROOT / "scripts" / "cost.py"
COST_PRICES = {"IN_USD_PER_MTOK": "1", "OUT_USD_PER_MTOK": "2"}
EXIT_BAD_COST_INPUT = 1


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


def cost_turn(booking: str, input_tokens: int, output_tokens: int) -> dict[str, object]:
    usage = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    return {"booking": booking, "usage": usage}


def write_cost_inputs(
    tmp_path: Path, turns: list[dict[str, object]], refs: list[str]
) -> tuple[Path, Path]:
    recording = tmp_path / "run.json"
    recording.write_text(json.dumps({"model": "test-model", "turns": turns}), encoding="utf-8")
    fixtures = tmp_path / "pnrs.json"
    fixtures.write_text(json.dumps({"pnrs": [{"pnr": ref} for ref in refs]}), encoding="utf-8")
    return recording, fixtures


def run_cost_script(
    recording: Path, fixtures: Path, prices: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    environ = {name: value for name, value in os.environ.items() if name not in COST_PRICES}
    return subprocess.run(
        [sys.executable, "-I", COST_SCRIPT, recording, fixtures],
        capture_output=True,
        text=True,
        check=False,
        env={**environ, **prices},
    )


def assert_cost_input_rejected(completed: subprocess.CompletedProcess[str], message: str) -> None:
    assert completed.returncode == EXIT_BAD_COST_INPUT
    assert completed.stdout == ""
    assert completed.stderr.startswith("error: ")
    assert message in completed.stderr


def test_cost_line_totals_recorded_turns(tmp_path: Path) -> None:
    turns = [
        cost_turn("AAA111", 1000, 100),
        cost_turn("AAA111", 500, 50),
        cost_turn("BBB222", 2000, 10),
    ]

    completed = run_cost_script(
        *write_cost_inputs(tmp_path, turns, ["AAA111", "BBB222", "CCC333"]), COST_PRICES
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == (
        "model=test-model input_tokens=3500 output_tokens=160 total_usd=0.003820"
        " model_bookings=2 code_settled_bookings=1 per_model_booking_usd=0.001910"
        " fixture_bookings=3 per_fixture_booking_usd=0.001273\n"
    )


def test_cost_line_rounds_a_tie_to_even(tmp_path: Path) -> None:
    prices = {"IN_USD_PER_MTOK": "0.5", "OUT_USD_PER_MTOK": "0"}

    completed = run_cost_script(*write_cost_inputs(tmp_path, [cost_turn("A", 5, 0)], ["A"]), prices)

    assert completed.returncode == 0, completed.stderr
    assert "total_usd=0.000002 " in completed.stdout


ONE_TURN = [cost_turn("A", 1, 1)]


@pytest.mark.parametrize(
    ("turns", "refs", "prices", "message"),
    [
        (ONE_TURN, ["A"], {"OUT_USD_PER_MTOK": "2"}, "set IN_USD_PER_MTOK"),
        (ONE_TURN, ["A"], {**COST_PRICES, "IN_USD_PER_MTOK": "abc"}, "plain decimal"),
        (ONE_TURN, ["A"], {**COST_PRICES, "IN_USD_PER_MTOK": "NaN"}, "plain decimal"),
        (ONE_TURN, ["A"], {**COST_PRICES, "OUT_USD_PER_MTOK": "-5"}, "plain decimal"),
        (ONE_TURN, ["A"], {**COST_PRICES, "IN_USD_PER_MTOK": "1_0"}, "plain decimal"),
        (ONE_TURN, ["A"], {**COST_PRICES, "IN_USD_PER_MTOK": "1" + "0" * 30}, "too large"),
        ([], ["A"], COST_PRICES, "no turns"),
        ([*ONE_TURN, cost_turn("B", 1, 1)], ["A"], COST_PRICES, "booking B is not in"),
        (ONE_TURN, ["A", "A"], COST_PRICES, "appears more than once"),
        ([cost_turn("A", -1, 1)], ["A"], COST_PRICES, "input_tokens is negative"),
        ([{"booking": "A"}], ["A"], COST_PRICES, "turn 0: usage is missing"),
    ],
    ids=[
        "missing-price",
        "price-not-a-number",
        "price-nan",
        "price-negative",
        "price-with-underscore",
        "price-too-large-to-print",
        "no-turns",
        "booking-not-in-fixtures",
        "duplicate-fixture-booking",
        "negative-tokens",
        "turn-without-usage",
    ],
)
def test_cost_script_rejects_bad_input(
    tmp_path: Path,
    turns: list[dict[str, object]],
    refs: list[str],
    prices: dict[str, str],
    message: str,
) -> None:
    completed = run_cost_script(*write_cost_inputs(tmp_path, turns, refs), prices)

    assert_cost_input_rejected(completed, message)


def test_cost_script_rejects_a_missing_recording(tmp_path: Path) -> None:
    _, fixtures = write_cost_inputs(tmp_path, ONE_TURN, ["A"])
    absent = tmp_path / "absent.json"

    completed = run_cost_script(absent, fixtures, COST_PRICES)

    assert_cost_input_rejected(completed, f"cannot read {absent}")


def test_cost_script_rejects_a_recording_that_is_not_json(tmp_path: Path) -> None:
    recording, fixtures = write_cost_inputs(tmp_path, ONE_TURN, ["A"])
    recording.write_text("{not json", encoding="utf-8")

    completed = run_cost_script(recording, fixtures, COST_PRICES)

    assert_cost_input_rejected(completed, f"cannot read {recording}")
