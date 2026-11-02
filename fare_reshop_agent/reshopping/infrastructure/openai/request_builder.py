from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal, TypedDict

from openai.types.responses import (
    EasyInputMessageParam,
    FunctionToolParam,
    ResponseFunctionToolCallParam,
    ResponseInputItemParam,
    ResponseTextConfigParam,
)
from openai.types.responses.response_input_item_param import FunctionCallOutput
from openai.types.shared_params import Reasoning

REASONING_EFFORT: Final = "none"


class ResponseRequest(TypedDict):
    model: str
    instructions: str
    input: list[ResponseInputItemParam]
    tools: list[FunctionToolParam]
    text: ResponseTextConfigParam
    reasoning: Reasoning
    store: Literal[False]
    parallel_tool_calls: Literal[False]
    max_output_tokens: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelSettings:
    model: str
    max_output_tokens: int


def build_request(
    *,
    settings: ModelSettings,
    instructions: str,
    input_items: Sequence[ResponseInputItemParam],
    tools: Sequence[FunctionToolParam],
    final_answer: ResponseTextConfigParam,
) -> ResponseRequest:
    return ResponseRequest(
        model=settings.model,
        instructions=instructions,
        input=list(input_items),
        tools=list(tools),
        text=final_answer,
        reasoning={"effort": REASONING_EFFORT},
        store=False,
        parallel_tool_calls=False,
        max_output_tokens=settings.max_output_tokens,
    )


def final_answer_format(*, name: str, schema: Mapping[str, object]) -> ResponseTextConfigParam:
    return {"format": {"type": "json_schema", "name": name, "schema": dict(schema), "strict": True}}


def function_tool(
    *, name: str, description: str, parameters: Mapping[str, object]
) -> FunctionToolParam:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": dict(parameters),
        "strict": True,
    }


def user_message(text: str) -> EasyInputMessageParam:
    return {"type": "message", "role": "user", "content": text}


def function_call_item(*, call_id: str, name: str, arguments: str) -> ResponseFunctionToolCallParam:
    return {"type": "function_call", "call_id": call_id, "name": name, "arguments": arguments}


def function_call_output_item(*, call_id: str, output: str) -> FunctionCallOutput:
    return {"type": "function_call_output", "call_id": call_id, "output": output}
