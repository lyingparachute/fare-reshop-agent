import dataclasses
import shutil
from pathlib import Path

import pytest

from fare_reshop_agent.reshopping.cli.doctor_output import render_doctor
from fare_reshop_agent.reshopping.cli.entry import EXIT_SETUP_ERROR
from fare_reshop_agent.reshopping.composition.doctor import recording_result
from fare_reshop_agent.reshopping.composition.recording import (
    check_recording,
    re_record_command,
    recording_path,
    replay_review,
)
from fare_reshop_agent.reshopping.composition.review import (
    EXCHANGE_RATES_FILE,
    POLICY_FILE,
    DataSet,
    data_set_folder,
    inspect_file_fix,
    review_prompt,
)
from fare_reshop_agent.reshopping.composition.setup_error import SetupError
from fare_reshop_agent.reshopping.infrastructure.json_files.recording_file import (
    read_recording,
    write_recording,
)
from fare_reshop_agent.reshopping.infrastructure.json_fixtures.source import JsonFixtureSource
from fare_reshop_agent.reshopping.infrastructure.toml.readers import (
    read_exchange_rates,
    read_policy,
)
from fare_reshop_agent.reshopping.orchestration.recording import RecordedTurns, compute_header
from fare_reshop_agent.reshopping.orchestration.replay import RecordedTrace, changed_inputs
from fare_reshop_agent.reshopping.orchestration.review import ReviewMode

from cli_process import REPO_ROOT, copied_repo_data, run_cli
from recording_data import header_of
from sample_data import PROMPT_FILE, InMemorySource, sample, usd

CARRIAGE_RETURN = b"\r"
SCENARIO_RESULT_COUNT = 6


@pytest.mark.parametrize("data_set", list(DataSet), ids=[data_set.value for data_set in DataSet])
def test_committed_recording_matches_data(
    data_set: DataSet, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(REPO_ROOT)
    snapshot = JsonFixtureSource(data_set_folder(data_set)).read_snapshot()
    current = compute_header(
        snapshot,
        read_exchange_rates(EXCHANGE_RATES_FILE).entries,
        read_policy(POLICY_FILE),
        review_prompt(),
    )

    recorded = read_recording(recording_path(data_set)).header

    changed = ", ".join(changed_inputs(current, recorded))
    assert current == recorded, (
        f"{changed} changed since the recording was made; a change to the prompt, the tool specs"
        f" or the review rules needs the owner's re-record: {re_record_command(data_set)}"
    )


@pytest.mark.parametrize(
    ("data_set", "result_count", "model_bookings"),
    [
        (DataSet.SAMPLE, 5, {"QX7T2A", "RT5K8B"}),
        (DataSet.SCENARIOS, 6, {"CH8L5F", "FD2N8Z", "MK3V7P", "RD9Q2X", "WJ6T4N"}),
    ],
    ids=[data_set.value for data_set in DataSet],
)
def test_committed_recording_replays(
    data_set: DataSet,
    result_count: int,
    model_bookings: set[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    report = replay_review(JsonFixtureSource(data_set_folder(data_set)), recording_path(data_set))

    assert report.mode is ReviewMode.RECORDED
    assert len(report.results) == result_count
    traces = {row.outcome.ref: row.trace for row in report.results}
    assert all(isinstance(trace, RecordedTrace) for trace in traces.values())
    replayed = {
        ref
        for ref, trace in traces.items()
        if isinstance(trace, RecordedTrace) and trace.trace.turns > 0
    }
    assert replayed == model_bookings


def test_committed_prompt_and_recording_are_lf() -> None:
    recordings = (REPO_ROOT / recording_path(data_set) for data_set in DataSet)
    for path in (PROMPT_FILE, *recordings):
        assert CARRIAGE_RETURN not in path.read_bytes(), f"{path} holds a carriage return"


def stale_doctor_lines(data_set: DataSet, folder: Path) -> list[str]:
    snapshot = JsonFixtureSource(data_set_folder(data_set)).read_snapshot()
    header = compute_header(
        snapshot,
        read_exchange_rates(EXCHANGE_RATES_FILE).entries,
        read_policy(POLICY_FILE),
        review_prompt(),
    )
    path = folder / recording_path(data_set).name
    write_recording(path, RecordedTurns(header=header, model="gpt-test", turns=()))
    first, *others = snapshot.offers
    changed = dataclasses.replace(
        snapshot, offers=(dataclasses.replace(first, price=first.price + usd("1.00")), *others)
    )
    result = recording_result(data_set, check_recording(InMemorySource(changed), path))
    return render_doctor([result]).splitlines()


def test_doctor_fails_when_recording_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)

    lines = stale_doctor_lines(DataSet.SAMPLE, tmp_path)

    assert lines == [
        f"[FAIL] the sample recording {tmp_path / 'review-run.json'} matches the data:"
        " fares_feed changed since it was recorded",
        "fix: uv run --env-file .env.local --extra live fare-reshop review"
        " --data sample --model openai --record",
    ]


def test_doctor_fails_when_scenario_recording_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(REPO_ROOT)

    lines = stale_doctor_lines(DataSet.SCENARIOS, tmp_path)

    assert lines == [
        f"[FAIL] the scenarios recording {tmp_path / 'scenarios-run.json'} matches the data:"
        " fares_feed changed since it was recorded",
        "fix: uv run --env-file .env.local --extra live fare-reshop review"
        " --data scenarios --model openai --record",
    ]


def test_scenario_replay_has_six_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    path = recording_path(DataSet.SCENARIOS)

    report = replay_review(JsonFixtureSource(data_set_folder(DataSet.SCENARIOS)), path)

    assert report.mode is ReviewMode.RECORDED
    assert len(report.results) == SCENARIO_RESULT_COUNT


def test_doctor_fails_when_recording_missing(tmp_path: Path) -> None:
    copied_repo_data(tmp_path)

    completed = run_cli("doctor", cwd=tmp_path)

    assert completed.returncode == EXIT_SETUP_ERROR
    lines = completed.stdout.splitlines()
    failed = lines.index(
        "[FAIL] the sample recording recordings/review-run.json matches the data:"
        " the file does not exist"
    )
    assert lines[failed + 1] == (
        "fix: uv run --env-file .env.local --extra live fare-reshop review"
        " --data sample --model openai --record"
    )


def test_recording_check_points_unreadable_input_to_its_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(copied_repo_data(tmp_path))
    shutil.copytree(REPO_ROOT / "recordings", tmp_path / "recordings")
    POLICY_FILE.unlink()
    path = recording_path(DataSet.SAMPLE)

    result = recording_result(
        DataSet.SAMPLE, check_recording(JsonFixtureSource(data_set_folder(DataSet.SAMPLE)), path)
    )

    assert render_doctor([result]).splitlines() == [
        f"[FAIL] the sample recording {path} matches the data:"
        f" {POLICY_FILE}: the file does not exist",
        f"fix: {inspect_file_fix(POLICY_FILE)}",
    ]


def test_doctor_names_amount_with_three_places(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(REPO_ROOT)
    snapshot = sample()
    first, *others = snapshot.offers
    too_precise = dataclasses.replace(
        snapshot, offers=(dataclasses.replace(first, price=first.price + usd("0.005")), *others)
    )
    path = tmp_path / "review-run.json"
    write_recording(path, RecordedTurns(header=header_of(snapshot), model="gpt-test", turns=()))

    result = recording_result(DataSet.SAMPLE, check_recording(InMemorySource(too_precise), path))

    error, fix = render_doctor([result]).splitlines()
    assert error.startswith(
        f"[FAIL] the sample recording {path} matches the data: money in a digest"
    )
    assert (
        fix == "fix: write every amount in the fixtures and config with at most two decimal places"
    )


def test_replay_of_amount_with_three_places_is_setup_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(REPO_ROOT)
    snapshot = sample()
    first, *others = snapshot.offers
    too_precise = dataclasses.replace(
        snapshot, offers=(dataclasses.replace(first, price=first.price + usd("0.005")), *others)
    )
    path = tmp_path / "review-run.json"
    write_recording(path, RecordedTurns(header=header_of(snapshot), model="gpt-test", turns=()))

    with pytest.raises(SetupError) as raised:
        replay_review(InMemorySource(too_precise), path)

    assert raised.value.error == "cannot digest the review inputs"
