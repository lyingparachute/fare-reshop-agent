import os
from collections.abc import Callable, Mapping
from enum import StrEnum
from importlib.resources import files
from pathlib import Path
from typing import assert_never

from fare_reshop_agent.reshopping.composition.live_model import (
    openai_model,
    provider_setup_error,
)
from fare_reshop_agent.reshopping.composition.setup_error import SetupError
from fare_reshop_agent.reshopping.infrastructure.file_problem import FileProblem, FileReadError
from fare_reshop_agent.reshopping.infrastructure.json_fixtures.source import (
    BOOKINGS_FILE,
    OFFERS_FILE,
    JsonFixtureSource,
)
from fare_reshop_agent.reshopping.infrastructure.openai.provider_errors import PROVIDER_REFUSALS
from fare_reshop_agent.reshopping.infrastructure.toml.readers import (
    read_exchange_rates,
    read_policy,
)
from fare_reshop_agent.reshopping.orchestration.agent_model import AgentModel, Prompt
from fare_reshop_agent.reshopping.orchestration.review import (
    ReviewAgent,
    ReviewMode,
    ReviewReport,
    review_snapshot,
    review_with_model,
)


class DataSet(StrEnum):
    SAMPLE = "sample"
    SCENARIOS = "scenarios"


SAMPLE_FOLDER = Path("fixtures")
SCENARIOS_FOLDER = Path("fixtures/scenarios")
PROMPT_PACKAGE = "fare_reshop_agent.reshopping.orchestration"
PROMPT_FILE = "review_prompt.md"
POLICY_FILE = Path("config/policy.toml")
EXCHANGE_RATES_FILE = Path("config/exchange_rates.toml")
REVIEW_FILES = (
    *(
        folder / name
        for folder in (SAMPLE_FOLDER, SCENARIOS_FOLDER)
        for name in (BOOKINGS_FILE, OFFERS_FILE)
    ),
    POLICY_FILE,
    EXCHANGE_RATES_FILE,
)


def review_without_model(data_set: DataSet) -> ReviewReport:
    try:
        return review_snapshot(
            JsonFixtureSource(data_set_folder(data_set)),
            read_exchange_rates(EXCHANGE_RATES_FILE),
            read_policy(POLICY_FILE),
        )
    except FileReadError as err:
        raise setup_error_for(err) from err


def review_with_live_model(
    data_set: DataSet,
    environ: Mapping[str, str],
    *,
    model_factory: Callable[[Mapping[str, str]], AgentModel] = openai_model,
) -> ReviewReport:
    model = model_factory(environ)
    prompt = Prompt(data=files(PROMPT_PACKAGE).joinpath(PROMPT_FILE).read_bytes())
    agent = ReviewAgent(model=model, prompt=prompt, mode=ReviewMode.OPENAI)
    try:
        return review_with_model(
            JsonFixtureSource(data_set_folder(data_set)),
            read_exchange_rates(EXCHANGE_RATES_FILE),
            read_policy(POLICY_FILE),
            agent,
        )
    except FileReadError as err:
        raise setup_error_for(err) from err
    except PROVIDER_REFUSALS as err:
        raise provider_setup_error(err) from err


def review_with_environment_model(data_set: DataSet) -> ReviewReport:
    return review_with_live_model(data_set, os.environ)


def data_set_folder(data_set: DataSet) -> Path:
    match data_set:
        case DataSet.SAMPLE:
            return SAMPLE_FOLDER
        case DataSet.SCENARIOS:
            return SCENARIOS_FOLDER
        case _:
            assert_never(data_set)


def inspect_file_fix(path: Path) -> str:
    return f"run from the repo root, then inspect with `git status` and `git diff -- {path}`"


def setup_error_for(err: FileReadError) -> SetupError:
    fix = inspect_file_fix(err.path)
    match err.problem:
        case FileProblem.MISSING:
            return SetupError(
                error=f"{err.path} is missing",
                reason=(
                    "the file does not exist; paths are read relative to the working"
                    " directory, which must be the repo root"
                ),
                fix=fix,
            )
        case FileProblem.UNREADABLE:
            return SetupError(
                error=f"{err.path} cannot be read",
                reason=f"the file cannot be opened as UTF-8 text: {err.fact}",
                fix=fix,
            )
        case FileProblem.MALFORMED:
            return SetupError(
                error=f"{err.path} is not valid",
                reason=err.fact,
                fix=fix,
            )
        case _:
            assert_never(err.problem)
