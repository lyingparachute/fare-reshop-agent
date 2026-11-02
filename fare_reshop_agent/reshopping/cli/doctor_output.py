from collections.abc import Sequence
from typing import assert_never

from fare_reshop_agent.reshopping.composition.doctor import CheckResult, Failed, Passed


def render_doctor(results: Sequence[CheckResult]) -> str:
    return "\n".join(_line(result) for result in results)


def _line(result: CheckResult) -> str:
    match result:
        case Passed():
            return f"[ok] {result.check}"
        case Failed():
            return f"[FAIL] {result.check}: {result.fact}\nfix: {result.fix}"
        case _:
            assert_never(result)
