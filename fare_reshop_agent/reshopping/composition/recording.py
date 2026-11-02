import dataclasses
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import assert_never

from fare_reshop_agent.reshopping.composition.live_model import openai_model, provider_setup_error
from fare_reshop_agent.reshopping.composition.review import (
    EXCHANGE_RATES_FILE,
    POLICY_FILE,
    DataSet,
    data_set_folder,
    review_prompt,
    setup_error_for,
)
from fare_reshop_agent.reshopping.composition.setup_error import SetupError
from fare_reshop_agent.reshopping.domain.exchange_rate import ExchangeRate
from fare_reshop_agent.reshopping.domain.port.reshop_source import ReshopSnapshot, ReshopSource
from fare_reshop_agent.reshopping.domain.terms import ReviewPolicy
from fare_reshop_agent.reshopping.infrastructure.file_problem import FileProblem, FileReadError
from fare_reshop_agent.reshopping.infrastructure.json_files.recording_file import (
    RecordingFileError,
    RecordingWriteError,
    read_recording,
    write_recording,
)
from fare_reshop_agent.reshopping.infrastructure.json_fixtures.source import JsonFixtureSource
from fare_reshop_agent.reshopping.infrastructure.openai.provider_errors import PROVIDER_REFUSALS
from fare_reshop_agent.reshopping.infrastructure.toml.readers import (
    read_exchange_rates,
    read_policy,
)
from fare_reshop_agent.reshopping.orchestration.agent_model import AgentModel, Prompt
from fare_reshop_agent.reshopping.orchestration.booking_loop import Trace
from fare_reshop_agent.reshopping.orchestration.booking_tools import tool_specs
from fare_reshop_agent.reshopping.orchestration.digests import (
    digest,
    fares_feed_projection,
    pnrs_projection,
    policy_projection,
    rates_projection,
    tools_projection,
)
from fare_reshop_agent.reshopping.orchestration.recording import (
    RecordingCompleted,
    RecordingHeader,
    RecordingModel,
    RecordingStopped,
)
from fare_reshop_agent.reshopping.orchestration.replay import (
    HeaderChanged,
    RecordedModel,
    RecordedTrace,
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

RECORDINGS_FOLDER = Path("recordings")
SAMPLE_RECORDING = "review-run.json"
SCENARIOS_RECORDING = "scenarios-run.json"


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordedRun:
    report: ReviewReport
    path: Path


def recording_path(data_set: DataSet) -> Path:
    match data_set:
        case DataSet.SAMPLE:
            return RECORDINGS_FOLDER / SAMPLE_RECORDING
        case DataSet.SCENARIOS:
            return RECORDINGS_FOLDER / SCENARIOS_RECORDING
        case _:
            assert_never(data_set)


def re_record_command(data_set: DataSet) -> str:
    return (
        "uv run --env-file .env.local --extra live fare-reshop review"
        f" --data {data_set.value} --model openai --record"
    )


def compute_header(
    snapshot: ReshopSnapshot, rates: Sequence[ExchangeRate], policy: ReviewPolicy, prompt: Prompt
) -> RecordingHeader:
    return RecordingHeader(
        pnrs=digest(pnrs_projection(snapshot)),
        fares_feed=digest(fares_feed_projection(snapshot)),
        policy=digest(policy_projection(policy)),
        rates=digest(rates_projection(rates)),
        prompt=prompt.version,
        tools=digest(tools_projection(tool_specs())),
    )


def record_review(
    source: ReshopSource, path: Path, model: AgentModel
) -> RecordedRun | RecordingStopped:
    try:
        rates = read_exchange_rates(EXCHANGE_RATES_FILE)
        policy = read_policy(POLICY_FILE)
        snapshot = source.read_snapshot()
    except FileReadError as err:
        raise setup_error_for(err) from err
    prompt = review_prompt()
    wrapper = RecordingModel(model, compute_header(snapshot, rates.entries, policy, prompt))
    agent = ReviewAgent(model=wrapper, prompt=prompt, mode=ReviewMode.OPENAI)
    report = review_with_model(_SnapshotSource(snapshot), rates, policy, agent)
    outcome = wrapper.outcome()
    match outcome:
        case RecordingStopped():
            return outcome
        case RecordingCompleted():
            _write(path, outcome)
            return RecordedRun(report=report, path=path)
        case _:
            assert_never(outcome)


def replay_review(source: ReshopSource, path: Path) -> ReviewReport:
    recorded = read_recording(path)
    try:
        rates = read_exchange_rates(EXCHANGE_RATES_FILE)
        policy = read_policy(POLICY_FILE)
        snapshot = source.read_snapshot()
    except FileReadError as err:
        raise setup_error_for(err) from err
    prompt = review_prompt()
    current = compute_header(snapshot, rates.entries, policy, prompt)
    changed = changed_inputs(current, recorded.header)
    if changed:
        raise StaleRecording(tuple(HeaderChanged(input=header_input) for header_input in changed))
    agent = ReviewAgent(model=RecordedModel(recorded), prompt=prompt, mode=ReviewMode.RECORDED)
    report = review_with_model(_SnapshotSource(snapshot), rates, policy, agent)
    turns_taken = {
        row.outcome.ref: row.trace.turns for row in report.results if isinstance(row.trace, Trace)
    }
    leftovers = leftover_turns(recorded, turns_taken)
    if leftovers:
        raise StaleRecording(leftovers)
    rows = tuple(_recorded_row(row, recorded.model) for row in report.results)
    return dataclasses.replace(report, results=rows)


def review_recorded(data_set: DataSet) -> ReviewReport:
    path = recording_path(data_set)
    try:
        return replay_review(JsonFixtureSource(data_set_folder(data_set)), path)
    except RecordingFileError as err:
        raise recording_setup_error(err, data_set) from err


def recording_setup_error(err: RecordingFileError, data_set: DataSet) -> SetupError:
    fix = f"uv run fare-reshop review --data {data_set.value} --model none"
    match err.problem:
        case FileProblem.MISSING:
            return SetupError(
                error=f"no recording at {err.path}",
                reason=(
                    "the recorded run replays that committed file,"
                    " and this checkout does not have it"
                ),
                fix=fix,
            )
        case FileProblem.UNREADABLE | FileProblem.MALFORMED:
            return SetupError(
                error=f"the recording {err.path} cannot be read",
                reason=err.fact,
                fix=fix,
            )
        case _:
            assert_never(err.problem)


def record_live_review(
    data_set: DataSet,
    environ: Mapping[str, str],
    *,
    model_factory: Callable[[Mapping[str, str]], AgentModel] = openai_model,
) -> RecordedRun | RecordingStopped:
    model = model_factory(environ)
    source = JsonFixtureSource(data_set_folder(data_set))
    try:
        return record_review(source, recording_path(data_set), model)
    except PROVIDER_REFUSALS as err:
        raise provider_setup_error(err) from err


def record_environment_review(data_set: DataSet) -> RecordedRun | RecordingStopped:
    return record_live_review(data_set, os.environ)


class _SnapshotSource:
    def __init__(self, snapshot: ReshopSnapshot) -> None:
        self._snapshot = snapshot

    def read_snapshot(self) -> ReshopSnapshot:
        return self._snapshot


def _recorded_row(row: ReviewRow, recorded_model: str) -> ReviewRow:
    match row.trace:
        case Trace():
            trace = RecordedTrace(trace=row.trace, recorded_model=recorded_model)
            return dataclasses.replace(row, trace=trace)
        case RecordedTrace() | None:
            return row
        case _:
            assert_never(row.trace)


def _write(path: Path, outcome: RecordingCompleted) -> None:
    try:
        write_recording(path, outcome.recorded)
    except RecordingWriteError as err:
        raise SetupError(
            error=f"cannot write the recording {err.path}",
            reason=err.reason,
            fix=f"make {err.path.parent} a writable folder, then record again",
        ) from err
