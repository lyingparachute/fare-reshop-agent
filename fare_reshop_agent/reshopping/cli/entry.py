import argparse
import sys
import traceback
from collections.abc import Sequence
from enum import StrEnum
from typing import NoReturn, assert_never, override

from fare_reshop_agent.reshopping.cli.doctor_output import render_doctor
from fare_reshop_agent.reshopping.cli.json_output import render_json
from fare_reshop_agent.reshopping.cli.table_output import render_table
from fare_reshop_agent.reshopping.composition.color import standard_output_color
from fare_reshop_agent.reshopping.composition.doctor import Failed, run_doctor
from fare_reshop_agent.reshopping.composition.review import DataSet, review_without_model
from fare_reshop_agent.reshopping.composition.setup_error import SetupError
from fare_reshop_agent.reshopping.orchestration.review import ReviewMode

PROGRAM_NAME = "fare-reshop"
REVIEW_COMMAND = "review"
DOCTOR_COMMAND = "doctor"
EXIT_INTERNAL_ERROR = 1
EXIT_SETUP_ERROR = 2


class OutputFormat(StrEnum):
    JSON = "json"
    TABLE = "table"


class _Parser(argparse.ArgumentParser):
    @override
    def error(self, message: str) -> NoReturn:
        raise SetupError(
            error=message,
            reason="the command line does not match what fare-reshop accepts",
            fix="see `uv run fare-reshop --help`",
        )


class _DataSetAction(argparse.Action):
    @override
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[object] | None,
        option_string: str | None = None,
    ) -> None:
        known = [data_set.value for data_set in DataSet]
        if values not in known:
            raise SetupError(
                error=f"unknown data set {values!r}",
                reason=f"only the configured data sets exist: {', '.join(known)}",
                fix="use " + " or ".join(f"--data {name}" for name in known),
            )
        setattr(namespace, self.dest, DataSet(values))


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
        choices=[mode.value for mode in ReviewMode],
        default=ReviewMode.NONE.value,
        help="who decides among eligible offers (default: %(default)s)",
    )
    review.add_argument(
        "--data",
        action=_DataSetAction,
        default=DataSet.SAMPLE,
        metavar="{" + ",".join(data_set.value for data_set in DataSet) + "}",
        help="which configured data set to review (default: %(default)s)",
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
    except SetupError as err:
        return _report_setup_error(err)
    try:
        if arguments.command == REVIEW_COMMAND:
            print(
                _render_review(
                    ReviewMode(arguments.model), arguments.data, OutputFormat(arguments.format)
                )
            )
        elif arguments.command == DOCTOR_COMMAND:
            return _doctor()
        else:
            parser.print_help()
    except SetupError as err:
        return _report_setup_error(err)
    except Exception as err:
        code = _report(
            EXIT_INTERNAL_ERROR,
            error=f"internal error: {type(err).__name__}: {err}",
            reason="this is a bug in fare-reshop, not a problem with your data or setup",
            fix=internal_error_fix(arguments.command),
        )
        if arguments.debug:
            traceback.print_exception(err, file=sys.stderr)
        return code
    return 0


def _render_review(mode: ReviewMode, data_set: DataSet, output_format: OutputFormat) -> str:
    match mode:
        case ReviewMode.NONE:
            report = review_without_model(data_set)
        case ReviewMode.OPENAI:
            raise SetupError(
                error="--model openai is not available in this build",
                reason="the live model path is not wired to the command line yet",
                fix="see `uv run fare-reshop --help`",
            )
        case _:
            assert_never(mode)
    match output_format:
        case OutputFormat.JSON:
            return render_json(report)
        case OutputFormat.TABLE:
            return render_table(report, standard_output_color())
        case _:
            assert_never(output_format)


def _doctor() -> int:
    results = run_doctor()
    print(render_doctor(results))
    return EXIT_SETUP_ERROR if any(isinstance(result, Failed) for result in results) else 0


def internal_error_fix(command: str) -> str:
    return f"uv run {PROGRAM_NAME} {command} --debug"


def error_lines(*, error: str, reason: str, fix: str) -> str:
    return "\n".join(
        f"{label}: {' '.join(text.split())}"
        for label, text in (("error", error), ("reason", reason), ("fix", fix))
    )


def _report_setup_error(err: SetupError) -> int:
    return _report(EXIT_SETUP_ERROR, error=err.error, reason=err.reason, fix=err.fix)


def _report(code: int, *, error: str, reason: str, fix: str) -> int:
    print(error_lines(error=error, reason=reason, fix=fix), file=sys.stderr)
    return code
