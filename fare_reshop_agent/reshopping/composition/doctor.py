import importlib
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import assert_never

from fare_reshop_agent.reshopping.composition.live_model import (
    KEY_VARIABLE,
    MODEL_VARIABLE,
    SYNC_LIVE_FIX,
    is_live_extra_installed,
    is_set,
    setting_fix,
)
from fare_reshop_agent.reshopping.composition.recording import (
    TWO_PLACES_FIX,
    InputNotDigestible,
    InputUnreadable,
    RecordingCheck,
    RecordingDiffers,
    RecordingMatches,
    RecordingUnreadable,
    check_recording,
    re_record_command,
    recording_path,
)
from fare_reshop_agent.reshopping.composition.review import (
    REVIEW_FILES,
    DataSet,
    data_set_folder,
    inspect_file_fix,
)
from fare_reshop_agent.reshopping.infrastructure.file_problem import FileReadError, read_text
from fare_reshop_agent.reshopping.infrastructure.json_fixtures.source import JsonFixtureSource

REQUIRED_MODULES = ("fare_reshop_agent", "pydantic")
SYNC_FIX = "uv sync"
OPTIONAL = "(optional, only for --model openai)"


@dataclass(frozen=True, slots=True, kw_only=True)
class Passed:
    check: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Failed:
    check: str
    fact: str
    fix: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OptionalMissing:
    check: str
    fix: str


type CheckResult = Passed | Failed | OptionalMissing


def run_doctor() -> tuple[CheckResult, ...]:
    return doctor_checks(os.environ)


def doctor_checks(environ: Mapping[str, str]) -> tuple[CheckResult, ...]:
    required = tuple(_module_check(name) for name in REQUIRED_MODULES) + tuple(
        _file_check(path) for path in REVIEW_FILES
    )
    recordings = tuple(_recording_check(data_set) for data_set in DataSet)
    return (*required, *recordings, *_live_checks(environ))


def recording_result(data_set: DataSet, check: RecordingCheck) -> CheckResult:
    name = f"the {data_set.value} recording {check.path} matches the data"
    match check:
        case RecordingMatches():
            return Passed(check=name)
        case RecordingDiffers():
            changed = ", ".join(check.changed)
            return Failed(
                check=name,
                fact=f"{changed} changed since it was recorded",
                fix=re_record_command(data_set),
            )
        case RecordingUnreadable():
            return Failed(check=name, fact=check.fact, fix=re_record_command(data_set))
        case InputNotDigestible():
            return Failed(check=name, fact=check.fact, fix=TWO_PLACES_FIX)
        case InputUnreadable():
            return Failed(
                check=name, fact=f"{check.file}: {check.fact}", fix=inspect_file_fix(check.file)
            )
        case _:
            assert_never(check)


def _recording_check(data_set: DataSet) -> CheckResult:
    path = recording_path(data_set)
    return recording_result(
        data_set, check_recording(JsonFixtureSource(data_set_folder(data_set)), path)
    )


def _live_checks(environ: Mapping[str, str]) -> tuple[CheckResult, ...]:
    extra = (
        Passed(check=f"the live extra is installed {OPTIONAL}")
        if is_live_extra_installed()
        else OptionalMissing(check=f"the live extra is not installed {OPTIONAL}", fix=SYNC_LIVE_FIX)
    )
    return (extra, *(_setting_check(environ, name) for name in (KEY_VARIABLE, MODEL_VARIABLE)))


def _setting_check(environ: Mapping[str, str], variable: str) -> CheckResult:
    if is_set(environ, variable):
        return Passed(check=f"{variable} is set {OPTIONAL}")
    return OptionalMissing(
        check=f"{variable} is not set {OPTIONAL}",
        fix=f"{setting_fix(variable)} for --model openai",
    )


def _module_check(name: str) -> CheckResult:
    check = f"the {name} package imports"
    try:
        importlib.import_module(name)
    except ImportError as err:
        return Failed(check=check, fact=str(err), fix=SYNC_FIX)
    return Passed(check=check)


def _file_check(path: Path) -> CheckResult:
    check = f"{path} is readable"
    try:
        read_text(path, FileReadError)
    except FileReadError as err:
        return Failed(check=check, fact=err.fact, fix=inspect_file_fix(path))
    return Passed(check=check)
