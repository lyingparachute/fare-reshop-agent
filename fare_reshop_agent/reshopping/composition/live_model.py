from collections.abc import Mapping
from importlib.util import find_spec
from typing import assert_never

from fare_reshop_agent.reshopping.composition.setup_error import SetupError
from fare_reshop_agent.reshopping.infrastructure.openai.provider_errors import (
    ProviderAuthenticationError,
    ProviderModelNotFoundError,
    ProviderPermissionError,
    ProviderRefusal,
)
from fare_reshop_agent.reshopping.orchestration.agent_model import AgentModel

KEY_VARIABLE = "OPENAI_API_KEY"
MODEL_VARIABLE = "OPENAI_MODEL"
LIVE_EXTRA_MODULE = "openai"
REQUEST_TIMEOUT_SECONDS = 60.0
MAX_OUTPUT_TOKENS = 2000
SYNC_LIVE_FIX = "run uv sync --extra live"
ENV_FILE = ".env.local"


def openai_model(environ: Mapping[str, str]) -> AgentModel:
    try:
        from openai import OpenAI

        from fare_reshop_agent.reshopping.infrastructure.openai.request_builder import (
            ModelSettings,
        )
        from fare_reshop_agent.reshopping.infrastructure.openai.responses_model import (
            OpenAIResponsesModel,
        )
    except ModuleNotFoundError as err:
        if err.name != LIVE_EXTRA_MODULE:
            raise
        raise SetupError(
            error="the live extra is not installed",
            reason="--model openai needs the openai package, which the live extra holds",
            fix=SYNC_LIVE_FIX,
        ) from err
    key = _setting(environ, KEY_VARIABLE, "the live model needs an OpenAI API key")
    model = _setting(environ, MODEL_VARIABLE, "the live model has no default model name")
    client = OpenAI(api_key=key, timeout=REQUEST_TIMEOUT_SECONDS)
    settings = ModelSettings(model=model, max_output_tokens=MAX_OUTPUT_TOKENS)
    return OpenAIResponsesModel(client=client.responses, settings=settings)


def is_live_extra_installed() -> bool:
    return find_spec(LIVE_EXTRA_MODULE) is not None


def setting_fix(variable: str) -> str:
    return f"set {variable} in {ENV_FILE} (see .env.example)"


def provider_setup_error(err: ProviderRefusal) -> SetupError:
    match err:
        case ProviderAuthenticationError():
            return SetupError(
                error="OpenAI rejected the API key",
                reason=str(err),
                fix=f"set {KEY_VARIABLE} in {ENV_FILE} to a valid key",
            )
        case ProviderPermissionError():
            return SetupError(
                error="OpenAI refused the model for this key",
                reason=str(err),
                fix=(
                    f"give the key access to the model in {MODEL_VARIABLE} in the OpenAI project"
                    f" settings, or set {MODEL_VARIABLE} in {ENV_FILE} to a model the key can use"
                ),
            )
        case ProviderModelNotFoundError():
            return SetupError(
                error="OpenAI refused the model name",
                reason=str(err),
                fix=(
                    f"set {MODEL_VARIABLE} in {ENV_FILE} to a model name that exists"
                    " (see .env.example)"
                ),
            )
        case _:
            assert_never(err)


def is_set(environ: Mapping[str, str], variable: str) -> bool:
    return bool(environ.get(variable))


def _setting(environ: Mapping[str, str], variable: str, reason: str) -> str:
    if not is_set(environ, variable):
        raise SetupError(
            error=f"{variable} is not set",
            reason=reason,
            fix=setting_fix(variable),
        )
    return environ[variable]
