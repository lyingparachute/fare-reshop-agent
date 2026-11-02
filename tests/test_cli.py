import subprocess
import sys
from pathlib import Path

FARE_RESHOP = Path(sys.executable).parent / "fare-reshop"


def test_console_entry_point_prints_help() -> None:
    completed = subprocess.run([FARE_RESHOP], capture_output=True, text=True, check=False)

    assert completed.returncode == 0
    assert completed.stdout.startswith("usage: fare-reshop")
