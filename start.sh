#!/bin/sh
set -u
cd "$(dirname "$0")" || exit 1

UV_INSTALL_COMMAND='curl -LsSf https://astral.sh/uv/install.sh | sh'

ask() {
    printf '%s [y/N] ' "$1"
    if read -r answer && [ "$answer" = "y" ]; then
        return 0
    fi
    printf '\n'
    return 1
}

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is not installed. uv installs Python, this project's packages and the fare-reshop command."
    echo "The official install command is: $UV_INSTALL_COMMAND"
    if ! ask "Install uv now?"; then
        echo "Nothing was installed. Install uv by hand with the command above, then run ./start.sh again."
        exit 1
    fi
    sh -c "$UV_INSTALL_COMMAND" || exit 1
    if ! command -v uv >/dev/null 2>&1; then
        echo "uv is installed but not on PATH yet. Open a new terminal and run ./start.sh again."
        exit 1
    fi
fi

if ! ask "Run uv sync now?"; then
    echo "Nothing was synced. Run this by hand, then run ./start.sh again: uv sync"
    exit 1
fi
uv sync || exit 1

uv run fare-reshop doctor || exit $?
uv run fare-reshop review
