#!/bin/sh
set -u
cd "$(dirname "$0")" || exit 1

UV_INSTALL_COMMAND='curl -LsSf https://astral.sh/uv/install.sh | sh'
UV_INSTALL_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
KEY_FILE=".env.local"
LIVE_PROMPT="An OpenAI key was found. Call the live model instead of replaying the recording? It makes paid API calls."

ask() {
    printf '%s [y/N] ' "$1"
    if read -r answer && [ "$answer" = "y" ]; then
        return 0
    fi
    printf '\n'
    return 1
}

heading() {
    printf '\n== %s ==\n\n' "$1"
}

has_key() {
    [ -n "${OPENAI_API_KEY:-}" ] && return 0
    [ -f "$KEY_FILE" ] && grep -Eq '^(export +)?OPENAI_API_KEY=[^"'"'"'[:space:]]' "$KEY_FILE"
}

review() {
    if [ "$LIVE" = "yes" ] && [ -f "$KEY_FILE" ]; then
        uv run --env-file "$KEY_FILE" --extra live fare-reshop review --model openai "$@"
    elif [ "$LIVE" = "yes" ]; then
        uv run --extra live fare-reshop review --model openai "$@"
    else
        uv run fare-reshop review "$@"
    fi
}

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is not installed. uv installs Python, this project's packages and the fare-reshop command."
    echo "The official install command is: $UV_INSTALL_COMMAND"
    if ! ask "Install uv now?"; then
        echo "Nothing was installed. Install uv by hand with the command above, then run ./start.sh again."
        exit 1
    fi
    sh -c "$UV_INSTALL_COMMAND" || exit 1
    PATH="$UV_INSTALL_DIR:$PATH"
    export PATH
    if ! command -v uv >/dev/null 2>&1; then
        echo "uv is installed but not on PATH yet. Open a new terminal and run ./start.sh again."
        exit 1
    fi
fi

if ! ask "Run uv sync now? It creates .venv in this folder and changes nothing else."; then
    echo "Nothing was synced. Run this by hand, then run ./start.sh again: uv sync"
    exit 1
fi
uv sync || exit 1

heading "Setup check"
uv run fare-reshop doctor || exit $?

LIVE="no"
RUN_NOTE="recorded model run, no key needed"
if has_key && ask "$LIVE_PROMPT"; then
    LIVE="yes"
    RUN_NOTE="live model run"
fi

heading "Sample bookings ($RUN_NOTE)"
review --format table || exit $?

heading "Judgment scenarios ($RUN_NOTE)"
review --data scenarios --format table || exit $?

heading "Try next"
echo "Full JSON, with every rule result and the model's reasoning:"
echo "  uv run fare-reshop review"
echo "Rules only, no model:"
echo "  uv run fare-reshop review --model none --format table"
echo "How it works: README.md and DESIGN.md"
