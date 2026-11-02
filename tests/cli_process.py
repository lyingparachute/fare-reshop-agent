import shutil
import subprocess
import sys
from pathlib import Path

FARE_RESHOP = Path(sys.executable).parent / "fare-reshop"
REPO_ROOT = Path(__file__).resolve().parent.parent


def run_cli(*arguments: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [FARE_RESHOP, *arguments], capture_output=True, text=True, check=False, cwd=cwd
    )


def copied_repo_data(tmp_path: Path) -> Path:
    for folder in ("fixtures", "config"):
        shutil.copytree(REPO_ROOT / folder, tmp_path / folder)
    return tmp_path
