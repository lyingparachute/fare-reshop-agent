#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -q
