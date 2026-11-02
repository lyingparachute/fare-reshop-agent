import importlib
from dataclasses import dataclass
from pathlib import Path

from fare_reshop_agent.reshopping.composition.review import REVIEW_FILES, inspect_file_fix
from fare_reshop_agent.reshopping.infrastructure.file_problem import FileReadError, read_text

REQUIRED_MODULES = ("fare_reshop_agent", "pydantic")
SYNC_FIX = "uv sync"


@dataclass(frozen=True, slots=True, kw_only=True)
class Passed:
    check: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Failed:
    check: str
    fact: str
    fix: str


type CheckResult = Passed | Failed


def run_doctor() -> tuple[CheckResult, ...]:
    return tuple(_module_check(name) for name in REQUIRED_MODULES) + tuple(
        _file_check(path) for path in REVIEW_FILES
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
