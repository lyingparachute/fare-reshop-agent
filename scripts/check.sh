#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
uv run --all-extras ruff format --check .
uv run --all-extras ruff check .
uv run --all-extras mypy
uv run --all-extras pytest -q
