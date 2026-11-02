import dataclasses
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from fare_reshop_agent.reshopping.cli.entry import (
    EXIT_SETUP_ERROR,
    EXIT_STALE_RECORDING,
    emit_stale_recording,
)
from fare_reshop_agent.reshopping.cli.json_output import render_json
from fare_reshop_agent.reshopping.composition.recording import (
    RecordedRun,
    re_record_command,
    record_review,
    replay_review,
)
from fare_reshop_agent.reshopping.composition.review import (
    DataSet,
)
from fare_reshop_agent.reshopping.domain.port.reshop_source import ReshopSnapshot
from fare_reshop_agent.reshopping.domain.trip import BookingRef
from fare_reshop_agent.reshopping.infrastructure.file_problem import FileProblem
from fare_reshop_agent.reshopping.infrastructure.json_files.recording_file import (
    RecordingFileError,
    read_recording,
    recording_text,
    write_recording,
)
from fare_reshop_agent.reshopping.infrastructure.json_fixtures.source import JsonFixtureSource
from fare_reshop_agent.reshopping.orchestration.agent_model import (
    ModelReply,
)
from fare_reshop_agent.reshopping.orchestration.agent_review import Incomplete
from fare_reshop_agent.reshopping.orchestration.booking_loop import (
    MAX_TURNS,
    IncompleteReason,
    Trace,
)
from fare_reshop_agent.reshopping.orchestration.recording import (
    RecordedTurns,
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
    ReviewRow,
    review_with_model,
)

from cli_process import REPO_ROOT, copied_repo_data, run_cli
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
    usd,
    with_bookings,
)
from scripted_model import ScriptedModel, call, calls, rebook

SAMPLE_REPLIES: dict[str, list[ModelReply]] = {
    "QX7T2A": [calls(call("get_booking")), rebook("OF-1001")],
    "RT5K8B": [rebook("OF-3001")],
}


def recorded_run(
    folder: Path, snapshot: ReshopSnapshot, scripts: dict[str, list[ModelReply]]
) -> RecordedRun:
    path = folder / "recordings" / "review-run.json"
    run = record_review(InMemorySource(snapshot), path, ScriptedModel(scripts))
    assert isinstance(run, RecordedRun)
    return run


SAMPLE_FIX_NONE = "fix: uv run fare-reshop review --data sample --model none"


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
    assert "docs/runbooks/re-record.md" in lines[1]
    assert lines[2] == SAMPLE_FIX_NONE


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
    assert lines[2] == "fix: uv run fare-reshop review --data scenarios --model none"


def test_booking_without_model_turns_leaves_every_turn_over() -> None:
    recorded = sample_recorded_turns()
    shuffled = dataclasses.replace(recorded, turns=tuple(reversed(recorded.turns)))

    assert leftover_turns(shuffled, {BookingRef("QX7T2A"): 1}) == (
        LeftoverTurn(booking=BookingRef("QX7T2A"), turn=2),
        LeftoverTurn(booking=BookingRef("RT5K8B"), turn=1),
    )
