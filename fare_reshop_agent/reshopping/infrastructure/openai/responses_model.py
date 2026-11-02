from dataclasses import dataclass
from typing import Protocol, Unpack, assert_never

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)
from openai.types.responses import (
    Response,
    ResponseFunctionToolCall,
    ResponseInputItemParam,
    ResponseOutputMessage,
    ResponseOutputRefusal,
    ResponseOutputText,
)

from fare_reshop_agent.reshopping.infrastructure.openai.provider_errors import (
    ProviderAuthenticationError,
    ProviderModelNotFoundError,
    ProviderPermissionError,
)
from fare_reshop_agent.reshopping.infrastructure.openai.request_builder import (
    ModelSettings,
    ResponseRequest,
    build_request,
    final_answer_format,
    function_call_item,
    function_call_output_item,
    function_tool,
    user_message,
)
from fare_reshop_agent.reshopping.orchestration.agent_model import (
    FinalText,
    ModelReply,
    ProviderErrorCode,
    ProviderFailed,
    Refusal,
    ToolCallItem,
    ToolCallRequest,
    ToolCalls,
    ToolResultItem,
    Transcript,
    TranscriptItem,
    Usage,
    UserMessage,
)
from fare_reshop_agent.reshopping.orchestration.final_answer import (
    FINAL_ANSWER_NAME,
    final_answer_schema,
)


class ResponsesClient(Protocol):
    def create(self, **request: Unpack[ResponseRequest]) -> Response: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class OpenAIResponsesModel:
    client: ResponsesClient
    settings: ModelSettings

    @property
    def model_name(self) -> str:
        return self.settings.model

    def next_step(self, transcript: Transcript) -> ModelReply:
        try:
            response = self.client.create(**self._request(transcript))
        except APITimeoutError:
            return ProviderFailed(code=ProviderErrorCode.TIMEOUT)
        except APIConnectionError:
            return ProviderFailed(code=ProviderErrorCode.CONNECTION)
        except RateLimitError:
            return ProviderFailed(code=ProviderErrorCode.RATE_LIMIT)
        except InternalServerError:
            return ProviderFailed(code=ProviderErrorCode.SERVER_ERROR)
        except AuthenticationError as err:
            raise ProviderAuthenticationError from err
        except PermissionDeniedError as err:
            raise ProviderPermissionError from err
        except NotFoundError as err:
            raise ProviderModelNotFoundError from err
        return _reply(response)

    def _request(self, transcript: Transcript) -> ResponseRequest:
        return build_request(
            settings=self.settings,
            instructions=transcript.prompt.text,
            input_items=[_input_item(item) for item in transcript.items],
            tools=[
                function_tool(
                    name=spec.name, description=spec.description, parameters=spec.parameters
                )
                for spec in transcript.tool_specs
            ],
            final_answer=final_answer_format(name=FINAL_ANSWER_NAME, schema=final_answer_schema()),
        )


def _input_item(item: TranscriptItem) -> ResponseInputItemParam:
    match item:
        case UserMessage():
            return user_message(item.text)
        case ToolCallItem():
            return function_call_item(
                call_id=item.call_id, name=item.name, arguments=item.arguments
            )
        case ToolResultItem():
            return function_call_output_item(call_id=item.call_id, output=item.result)
        case _:
            assert_never(item)


def _reply(response: Response) -> ModelReply:
    usage = _usage(response)
    calls: list[ToolCallRequest] = []
    texts: list[str] = []
    refusals: list[str] = []
    for item in response.output:
        if isinstance(item, ResponseFunctionToolCall):
            calls.append(ToolCallRequest(name=item.name, arguments=item.arguments))
        elif isinstance(item, ResponseOutputMessage):
            for part in item.content:
                if isinstance(part, ResponseOutputText):
                    texts.append(part.text)
                elif isinstance(part, ResponseOutputRefusal):
                    refusals.append(part.refusal)
    text = "".join(texts)
    if refusals:
        return Refusal(text="".join(refusals), usage=usage)
    if calls:
        return ToolCalls(calls=tuple(calls), text=text or None, usage=usage)
    return FinalText(text=text, usage=usage)


def _usage(response: Response) -> Usage:
    if response.usage is None:
        raise ValueError("an OpenAI response carried no token usage")
    return Usage(
        input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens
    )
