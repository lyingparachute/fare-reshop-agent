import argparse
import sys
import traceback
from collections.abc import Sequence
from enum import StrEnum
from typing import NoReturn, assert_never, override

from fare_reshop_agent.reshopping.cli.json_output import render_json
from fare_reshop_agent.reshopping.cli.table_output import render_table
from fare_reshop_agent.reshopping.composition.color import standard_output_color
from fare_reshop_agent.reshopping.composition.doctor import Failed, Passed, run_doctor
from fare_reshop_agent.reshopping.composition.review import review_without_model
from fare_reshop_agent.reshopping.composition.setup_error import SetupError

PROGRAM_NAME = "fare-reshop"
REVIEW_COMMAND = "review"
DOCTOR_COMMAND = "doctor"
MODEL_NONE = "none"
EXIT_INTERNAL_ERROR = 1
EXIT_SETUP_ERROR = 2
INTERNAL_ERROR_FIX = "uv run fare-reshop review --debug"


class OutputFormat(StrEnum):
    JSON = "json"
    TABLE = "table"


class ArgumentProblem(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    @override
    def error(self, message: str) -> NoReturn:
        raise ArgumentProblem(message)


def build_parser() -> argparse.ArgumentParser:
    common = _Parser(add_help=False)
    common.add_argument(
        "--debug", action="store_true", help="print the traceback of an internal error"
    )
    parser = _Parser(
        prog=PROGRAM_NAME,
        description="Compare booked flights with fares on sale now.",
    )
    parser.set_defaults(debug=False)
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    review = commands.add_parser(
        REVIEW_COMMAND, parents=[common], help="recommend rebook or keep for every booking"
    )
    review.add_argument(
        "--model",
        choices=[MODEL_NONE],
        default=MODEL_NONE,
        help="who decides among eligible offers (default: %(default)s)",
    )
    review.add_argument(
        "--format",
        choices=[output_format.value for output_format in OutputFormat],
        default=OutputFormat.JSON.value,
        help="output format (default: %(default)s)",
    )
    commands.add_parser(
        DOCTOR_COMMAND, parents=[common], help="check that everything the review needs is in place"
    )
    return parser


def main() -> None:
    sys.exit(run(sys.argv[1:]))


def run(argv: Sequence[str]) -> int:
    parser = build_parser()
    try:
        arguments = parser.parse_args(argv)
    except ArgumentProblem as problem:
        return _report(
            EXIT_SETUP_ERROR,
            error=str(problem),
            reason="the command line does not match what fare-reshop accepts",
            fix="see `uv run fare-reshop --help`",
        )
    debug: bool = arguments.debug
    try:
        if arguments.command == REVIEW_COMMAND:
            print(_render_review(OutputFormat(arguments.format)))
        elif arguments.command == DOCTOR_COMMAND:
            return _doctor()
        else:
            parser.print_help()
    except SetupError as err:
        return _report(EXIT_SETUP_ERROR, error=err.error, reason=err.reason, fix=err.fix)
    except Exception as err:
        code = _report(
            EXIT_INTERNAL_ERROR,
            error=f"internal error: {type(err).__name__}: {err}",
            reason="this is a bug in fare-reshop, not a problem with your data or setup",
            fix=INTERNAL_ERROR_FIX,
        )
        if debug:
            traceback.print_exception(err, file=sys.stderr)
        return code
    return 0


def _render_review(output_format: OutputFormat) -> str:
    report = review_without_model()
    match output_format:
        case OutputFormat.JSON:
            return render_json(report)
        case OutputFormat.TABLE:
            return render_table(report, standard_output_color())
        case _:
            assert_never(output_format)


def _doctor() -> int:
    results = run_doctor()
    for result in results:
        match result:
            case Passed():
                print(f"[ok] {result.check}")
            case Failed():
                print(f"[FAIL] {result.check}: {result.fact}\nfix: {result.fix}")
            case _:
                assert_never(result)
    return EXIT_SETUP_ERROR if any(isinstance(r, Failed) for r in results) else 0


def error_lines(*, error: str, reason: str, fix: str) -> str:
    return "\n".join(
        f"{label}: {' '.join(text.split())}"
        for label, text in (("error", error), ("reason", reason), ("fix", fix))
    )


def _report(code: int, *, error: str, reason: str, fix: str) -> int:
    print(error_lines(error=error, reason=reason, fix=fix), file=sys.stderr)
    return code
