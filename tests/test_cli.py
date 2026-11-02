import json
import os
import pty
import select
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from fare_reshop_agent.reshopping.cli.entry import error_lines, internal_error_fix
from fare_reshop_agent.reshopping.composition.review import (
    REVIEW_FILES,
    DataSet,
    review_without_model,
)
from fare_reshop_agent.reshopping.composition.setup_error import SetupError

FARE_RESHOP = Path(sys.executable).parent / "fare-reshop"
REPO_ROOT = Path(__file__).resolve().parent.parent
TOP_LEVEL_KEYS = ["schema_version", "mode", "as_of", "data_issues", "results"]
RESULT_KEYS = [
    "pnr",
    "status",
    "rebook",
    "decided_by",
    "incomplete_reason",
    "offer_id",
    "nominal_saving",
    "approval_flags",
    "confidence",
    "reasoning",
    "minimum_saving",
    "exchange_rates",
    "invalid_reason",
    "evaluations",
]
EVALUATION_KEYS = ["offer_id", "rules", "nominal_saving", "exchange_rates", "approval_flags"]
RULE_ORDER = [
    "cabin",
    "refundable",
    "bags",
    "stops",
    "seats",
    "future_change_fee",
    "exchange_rate",
]


def run_cli(*arguments: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [FARE_RESHOP, *arguments], capture_output=True, text=True, check=False, cwd=cwd
    )


def copied_repo_data(tmp_path: Path) -> Path:
    for folder in ("fixtures", "config"):
        shutil.copytree(REPO_ROOT / folder, tmp_path / folder)
    return tmp_path


def test_console_entry_point_prints_help() -> None:
    completed = run_cli()

    assert completed.returncode == 0
    assert completed.stdout.startswith("usage: fare-reshop")


def test_review_json_has_schema_version_one() -> None:
    completed = run_cli("review", "--model", "none")

    document = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert document["schema_version"] == 1
    assert document["mode"] == "none"
    assert list(document) == TOP_LEVEL_KEYS


def test_json_output_is_deterministic() -> None:
    first = run_cli("review", "--model", "none")
    second = run_cli("review", "--model", "none")

    assert first.returncode == 0
    assert first.stdout == second.stdout


def test_empty_bookings_exit_0(tmp_path: Path) -> None:
    root = copied_repo_data(tmp_path)
    (root / "fixtures" / "pnrs.json").write_text('{"pnrs": []}', encoding="utf-8")

    completed = run_cli("review", "--model", "none", cwd=root)

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["results"] == []


def test_invalid_booking_has_the_invalid_data_shape(tmp_path: Path) -> None:
    root = copied_repo_data(tmp_path)
    bookings_path = root / "fixtures" / "pnrs.json"
    bookings_path.write_text(
        bookings_path.read_text(encoding="utf-8").replace('"passengers": 1', '"passengers": 0', 1),
        encoding="utf-8",
    )

    completed = run_cli("review", "--model", "none", cwd=root)

    result = json.loads(completed.stdout)["results"][2]
    assert result == {
        "pnr": "QX7T2A",
        "status": "INVALID_DATA",
        "rebook": False,
        "decided_by": "rules",
        "incomplete_reason": None,
        "offer_id": None,
        "nominal_saving": None,
        "approval_flags": [],
        "confidence": None,
        "reasoning": None,
        "minimum_saving": None,
        "exchange_rates": [],
        "invalid_reason": "passengers must be at least 1, got 0",
        "evaluations": [],
    }


def test_rebook_result_shows_saving_minimum_and_rates() -> None:
    results = json.loads(run_cli("review", "--model", "none").stdout)["results"]

    rt5k8b = next(result for result in results if result["pnr"] == "RT5K8B")
    assert rt5k8b["status"] == "REBOOK"
    assert rt5k8b["rebook"] is True
    assert rt5k8b["offer_id"] == "OF-3001"
    assert rt5k8b["nominal_saving"] == {"amount": "363.21", "currency": "EUR"}
    assert rt5k8b["minimum_saving"] == {"amount": "43.73", "currency": "EUR"}
    assert rt5k8b["exchange_rates"] == [
        {
            "use": "minimum_saving",
            "rate": "1.1433",
            "direction": "1 EUR = 1.1433 USD",
            "as_of": "2026-07-07",
        }
    ]
    assert [rate["use"] for rate in rt5k8b["evaluations"][0]["exchange_rates"]] == [
        "offer_price",
        "offer_change_fee",
    ]


def test_result_and_evaluation_keys_keep_their_order() -> None:
    results = json.loads(run_cli("review", "--model", "none").stdout)["results"]

    assert all(list(result) == RESULT_KEYS for result in results)
    evaluations = [e for result in results for e in result["evaluations"]]
    assert all(list(evaluation) == EVALUATION_KEYS for evaluation in evaluations)
    assert all([rule["rule"] for rule in e["rules"]] == RULE_ORDER for e in evaluations)


def test_bad_offer_is_listed_under_data_issues(tmp_path: Path) -> None:
    root = copied_repo_data(tmp_path)
    offers_path = root / "fixtures" / "fares_feed.json"
    offers_path.write_text(
        offers_path.read_text(encoding="utf-8").replace(
            '"seatsAvailable": 5', '"seatsAvailable": -5'
        ),
        encoding="utf-8",
    )

    document = json.loads(run_cli("review", "--model", "none", cwd=root).stdout)

    assert document["data_issues"] == [
        {
            "kind": "offer_rejected",
            "id": "OF-1001",
            "reason": "seats available must be zero or more, got -5",
        }
    ]


@pytest.mark.parametrize(
    ("break_repo", "error", "reason"),
    [
        (
            lambda root: (root / "config" / "exchange_rates.toml").unlink(),
            "config/exchange_rates.toml is missing",
            "relative to the working directory",
        ),
        (
            lambda root: (root / "config" / "policy.toml").write_text("[", encoding="utf-8"),
            "config/policy.toml is not valid",
            "Invalid initial character",
        ),
        (
            lambda root: (root / "fixtures" / "pnrs.json").write_bytes(b"\xff"),
            "fixtures/pnrs.json cannot be read",
            "UTF-8",
        ),
    ],
)
def test_file_problems_become_setup_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    break_repo: Callable[[Path], object],
    error: str,
    reason: str,
) -> None:
    root = copied_repo_data(tmp_path)
    break_repo(root)
    monkeypatch.chdir(root)

    with pytest.raises(SetupError) as raised:
        review_without_model(DataSet.SAMPLE)

    assert raised.value.error == error
    assert reason in raised.value.reason
    assert "git diff -- " in raised.value.fix


ESCAPE = "\033["
EXIT_INTERNAL_ERROR = 1
EXIT_SETUP_ERROR = 2
ERROR_PREFIXES = ["error", "reason", "fix"]
TERMINAL_TIMEOUT_SECONDS = 30
TERMINAL_READ_BYTES = 4096


def run_on_terminal(*arguments: str, environ: Mapping[str, str]) -> str:
    controller, terminal = pty.openpty()
    try:
        process = subprocess.Popen(
            [FARE_RESHOP, *arguments],
            stdout=terminal,
            stderr=subprocess.DEVNULL,
            cwd=REPO_ROOT,
            env=environ,
        )
        os.close(terminal)
        terminal = -1
        try:
            output = read_until_closed(controller, time.monotonic() + TERMINAL_TIMEOUT_SECONDS)
            process.wait(timeout=TERMINAL_TIMEOUT_SECONDS)
        finally:
            process.kill()
            process.wait()
    finally:
        os.close(controller)
        if terminal != -1:
            os.close(terminal)
    return output.decode("utf-8")


def read_until_closed(descriptor: int, deadline: float) -> bytes:
    output = b""
    while True:
        remaining = deadline - time.monotonic()
        ready, _, _ = select.select([descriptor], [], [], max(remaining, 0))
        if not ready:
            raise TimeoutError(f"no terminal output within {TERMINAL_TIMEOUT_SECONDS} seconds")
        try:
            chunk = os.read(descriptor, TERMINAL_READ_BYTES)
        except OSError:
            return output
        if not chunk:
            return output
        output += chunk


def three_lines(stderr: str) -> list[str]:
    return [line.split(":", 1)[0] for line in stderr.splitlines()[:3]]


def test_table_output_has_no_color_when_piped() -> None:
    completed = run_cli("review", "--model", "none", "--format", "table")

    assert completed.returncode == 0
    assert "QX7T2A  REBOOK" in completed.stdout
    assert ESCAPE not in completed.stdout


def test_no_color_variable_turns_color_off() -> None:
    output = run_on_terminal("review", "--format", "table", environ={**os.environ, "NO_COLOR": "1"})

    assert "REBOOK" in output
    assert ESCAPE not in output


def test_table_output_is_colored_on_a_terminal() -> None:
    environ = {key: value for key, value in os.environ.items() if key != "NO_COLOR"}

    output = run_on_terminal("review", "--format", "table", environ=environ)

    assert f"{ESCAPE}32mREBOOK" in output


def test_error_format_for_missing_fixture_has_three_lines(tmp_path: Path) -> None:
    root = copied_repo_data(tmp_path)
    (root / "fixtures" / "pnrs.json").unlink()

    completed = run_cli("review", cwd=root)

    assert completed.returncode == EXIT_SETUP_ERROR
    assert completed.stdout == ""
    assert three_lines(completed.stderr) == ERROR_PREFIXES
    assert len(completed.stderr.splitlines()) == len(ERROR_PREFIXES)
    assert "fixtures/pnrs.json is missing" in completed.stderr
    assert "git diff" in completed.stderr
    assert "git checkout" not in completed.stderr


def test_error_format_hides_traceback_without_debug(tmp_path: Path) -> None:
    root = copied_repo_data(tmp_path)
    (root / "fixtures" / "pnrs.json").write_text("[" * 100_000, encoding="utf-8")

    completed = run_cli("review", cwd=root)

    assert completed.returncode == EXIT_INTERNAL_ERROR
    assert three_lines(completed.stderr) == ERROR_PREFIXES
    assert not any(line.startswith("Traceback") for line in completed.stderr.splitlines())


def test_debug_flag_prints_traceback(tmp_path: Path) -> None:
    root = copied_repo_data(tmp_path)
    (root / "fixtures" / "pnrs.json").write_text("[" * 100_000, encoding="utf-8")

    completed = run_cli("review", "--debug", cwd=root)

    lines = completed.stderr.splitlines()
    assert completed.returncode == EXIT_INTERNAL_ERROR
    assert three_lines(completed.stderr) == ERROR_PREFIXES
    assert lines[2] == "fix: uv run fare-reshop review --debug"
    assert lines[3] == "Traceback (most recent call last):"
    assert lines[-1].startswith("RecursionError")


def test_internal_error_fix_names_the_failing_command() -> None:
    assert internal_error_fix("doctor") == "uv run fare-reshop doctor --debug"


def test_error_format_for_unknown_model() -> None:
    completed = run_cli("review", "--model", "openai")

    assert completed.returncode == EXIT_SETUP_ERROR
    assert three_lines(completed.stderr) == ERROR_PREFIXES
    assert len(completed.stderr.splitlines()) == len(ERROR_PREFIXES)
    assert "--help" in completed.stderr.splitlines()[2]


def test_missing_policy_file_exits_2(tmp_path: Path) -> None:
    root = copied_repo_data(tmp_path)
    (root / "config" / "policy.toml").unlink()

    completed = run_cli("review", cwd=root)

    assert completed.returncode == EXIT_SETUP_ERROR
    assert three_lines(completed.stderr) == ERROR_PREFIXES
    assert "config/policy.toml is missing" in completed.stderr


def test_error_lines_stay_three_lines_for_a_multi_line_message() -> None:
    text = error_lines(error="first line\nsecond line", reason="why", fix="do this")

    assert text.splitlines() == [
        "error: first line second line",
        "reason: why",
        "fix: do this",
    ]


def test_table_shows_invalid_rows_empty_routes_and_data_issues(tmp_path: Path) -> None:
    root = copied_repo_data(tmp_path)
    bookings_path = root / "fixtures" / "pnrs.json"
    bookings_path.write_text(
        bookings_path.read_text(encoding="utf-8").replace('"passengers": 1', '"passengers": 0', 1),
        encoding="utf-8",
    )
    offers_path = root / "fixtures" / "fares_feed.json"
    offers_path.write_text(
        offers_path.read_text(encoding="utf-8").replace(
            '"departureDate": "2026-09-02"', '"departureDate": "2026-09-03"'
        ),
        encoding="utf-8",
    )

    lines = run_cli("review", "--format", "table", cwd=root).stdout.splitlines()

    assert lines == [
        "PNR     STATUS        OFFER    SAVING      REASON",
        "HB6W9E  KEEP          -        -           No offer reaches the minimum.",
        "LM9P4C  KEEP          -        -           No offers on this route and date.",
        "QX7T2A  INVALID_DATA  -        -           passengers must be at least 1, got 0",
        "RT5K8B  REBOOK        OF-3001  363.21 EUR  -",
        "ZC3N1D  KEEP          -        -           No offer passes every rule.",
        "data issue: offer_rejected OF-2001: route.departureDate 2026-09-03 differs from the"
        " departure 2026-09-02 13:10:00",
    ]


START_SCRIPT = REPO_ROOT / "start.sh"
SYSTEM_PATH = "/usr/bin:/bin"


def run_start_script(path: str, answers: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [START_SCRIPT],
        input=answers,
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": path, "HOME": os.environ["HOME"]},
    )


def test_doctor_passes_on_synced_checkout() -> None:
    completed = run_cli("doctor")

    assert completed.returncode == 0
    lines = completed.stdout.splitlines()
    assert lines
    assert all(line.startswith("[ok] ") for line in lines)


def test_doctor_names_fix_for_missing_fixture(tmp_path: Path) -> None:
    for index, path in enumerate(REVIEW_FILES):
        root = copied_repo_data(tmp_path / str(index))
        (root / path).unlink()

        completed = run_cli("doctor", cwd=root)

        lines = completed.stdout.splitlines()
        failed = lines.index(f"[FAIL] {path} is readable: the file does not exist")
        assert lines[failed + 1].startswith("fix: ")
        assert f"git diff -- {path}" in lines[failed + 1]
        assert completed.returncode == EXIT_SETUP_ERROR, path


def test_start_script_asks_before_install() -> None:
    completed = run_start_script(SYSTEM_PATH, answers="")

    assert "Install uv now? [y/N]" in completed.stdout
    assert "Nothing was installed." in completed.stdout
    assert completed.returncode == 1


def test_start_script_asks_before_sync() -> None:
    uv = shutil.which("uv")
    assert uv is not None, "the tests run through uv, so uv must be on PATH"

    completed = run_start_script(f"{Path(uv).parent}:{SYSTEM_PATH}", answers="n\n")

    assert "Install uv now?" not in completed.stdout
    assert "Run uv sync now? [y/N]" in completed.stdout
    assert "Nothing was synced." in completed.stdout
    assert completed.returncode == 1


def test_data_scenarios_prints_six_results() -> None:
    completed = run_cli("review", "--data", "scenarios")

    assert completed.returncode == 0
    assert [result["pnr"] for result in json.loads(completed.stdout)["results"]] == [
        "CH8L5F",
        "FD2N8Z",
        "MK3V7P",
        "RD9Q2X",
        "WJ6T4N",
        "YU6EG1",
    ]


def test_data_default_is_sample() -> None:
    default = run_cli("review")
    sample = run_cli("review", "--data", "sample")

    assert default.returncode == 0
    assert default.stdout == sample.stdout


def test_unknown_data_set_exits_2_three_lines() -> None:
    completed = run_cli("review", "--data", "nope")

    assert completed.returncode == EXIT_SETUP_ERROR
    assert completed.stderr.splitlines() == [
        "error: unknown data set 'nope'",
        "reason: only the configured data sets exist: sample, scenarios",
        "fix: use --data sample or --data scenarios",
    ]


@pytest.mark.parametrize("data_set", ["sample", "scenarios"])
def test_rules_only_output_matches_golden_file(data_set: str) -> None:
    golden = REPO_ROOT / "tests" / "golden" / f"review-none-{data_set}.json"

    completed = run_cli("review", "--model", "none", "--data", data_set)

    assert completed.stdout == golden.read_text(encoding="utf-8")
