import json
from dataclasses import dataclass
from decimal import Decimal
from typing import NoReturn, TypeGuard

from fare_reshop_agent.reshopping.orchestration.agent_model import ToolCallRequest
from fare_reshop_agent.reshopping.orchestration.canonical_json import (
    TEXT_ENCODING,
    JsonValue,
    canonical_json,
)

MAX_NUMBER_MAGNITUDE = 18


@dataclass(frozen=True, slots=True, kw_only=True)
class Malformed:
    reason: str


def parse_json_object(text: str) -> dict[str, JsonValue] | Malformed:
    try:
        parsed: object = json.loads(
            text, parse_float=_number, parse_int=_number, parse_constant=_reject_constant
        )
        if not isinstance(parsed, dict):
            return Malformed(reason="not a JSON object")
        canonical_json(parsed)
    except (ValueError, ArithmeticError, RecursionError) as err:
        return Malformed(reason=f"not usable JSON: {type(err).__name__}")
    return parsed


def canonical_arguments(call: ToolCallRequest) -> str:
    arguments = parse_json_object(call.arguments)
    if isinstance(arguments, Malformed):
        return call.arguments
    return canonical_json(arguments)


def is_text(value: object) -> TypeGuard[str]:
    if not isinstance(value, str):
        return False
    try:
        value.encode(TEXT_ENCODING)
    except UnicodeEncodeError:
        return False
    return True


def _number(text: str) -> Decimal:
    number = Decimal(text)
    if abs(number.adjusted()) > MAX_NUMBER_MAGNITUDE:
        raise ValueError(f"the number {text[:20]} is out of range")
    return number


def _reject_constant(name: str) -> NoReturn:
    raise ValueError(f"{name} is not a finite number")
