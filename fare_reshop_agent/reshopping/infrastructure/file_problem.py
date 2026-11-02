from collections.abc import Callable
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

DATE_FORMAT = "%Y-%m-%d"
DATE_EXAMPLE = "2026-08-15"


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FileProblem(StrEnum):
    MISSING = "missing"
    UNREADABLE = "unreadable"
    MALFORMED = "malformed"


class FileReadError(Exception):
    def __init__(self, *, path: Path, problem: FileProblem, fact: str) -> None:
        super().__init__(f"{path}: {problem}: {fact}")
        self.path = path
        self.problem = problem
        self.fact = fact


def read_text(path: Path, error: type[FileReadError]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as err:
        raise error(path=path, problem=FileProblem.MISSING, fact="the file does not exist") from err
    except (OSError, UnicodeDecodeError) as err:
        raise error(path=path, problem=FileProblem.UNREADABLE, fact=str(err)) from err


def validation_fact(error: ValidationError) -> str:
    first = error.errors()[0]
    location = ".".join(str(part) for part in first["loc"])
    return f"{location}: {first['msg']}" if location else str(first["msg"])


def read_model[Model: BaseModel](
    path: Path,
    model: type[Model],
    error: type[FileReadError],
    parse: Callable[[str], object],
    decode_error: type[ValueError],
) -> Model:
    text = read_text(path, error)
    try:
        return model.model_validate(parse(text))
    except decode_error as err:
        raise error(path=path, problem=FileProblem.MALFORMED, fact=str(err)) from err
    except ValidationError as err:
        raise error(path=path, problem=FileProblem.MALFORMED, fact=validation_fact(err)) from err


def exact_time(text: str, time_format: str, example: str) -> datetime:
    try:
        parsed = datetime.strptime(text, time_format)
    except ValueError as err:
        raise ValueError(f"{text!r} is not a time like {example}") from err
    if parsed.strftime(time_format) != text:
        raise ValueError(f"{text!r} is not a time like {example}")
    return parsed


def exact_date(text: str) -> date:
    return exact_time(text, DATE_FORMAT, DATE_EXAMPLE).date()
