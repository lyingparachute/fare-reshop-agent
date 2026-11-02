from dataclasses import dataclass, field
from typing import Unpack

from openai import APIError
from openai.types.responses import Response

from fare_reshop_agent.reshopping.infrastructure.openai.request_builder import (
    ModelSettings,
    ResponseRequest,
)

STUB_RESPONSE_ID = "resp_1"


@dataclass(slots=True, kw_only=True)
class StubResponsesClient:
    outcome: Response | APIError
    requests: list[ResponseRequest] = field(default_factory=list)

    def create(self, **request: Unpack[ResponseRequest]) -> Response:
        self.requests.append(request)
        if isinstance(self.outcome, APIError):
            raise self.outcome
        return self.outcome


STUB_SETTINGS = ModelSettings(model="gpt-test", max_output_tokens=2000)


def stub_response(output: list[dict[str, object]], response_id: str = STUB_RESPONSE_ID) -> Response:
    return Response.model_validate(
        {
            "id": response_id,
            "created_at": 1,
            "model": "gpt-test",
            "object": "response",
            "output": output,
            "parallel_tool_calls": False,
            "tool_choice": "auto",
            "tools": [],
            "status": "completed",
            "usage": {
                "input_tokens": 120,
                "input_tokens_details": {"cache_write_tokens": 0, "cached_tokens": 0},
                "output_tokens": 30,
                "output_tokens_details": {"reasoning_tokens": 0},
                "total_tokens": 150,
            },
        }
    )


def stub_message(*content: dict[str, object]) -> dict[str, object]:
    return {
        "type": "message",
        "id": "msg_1",
        "role": "assistant",
        "status": "completed",
        "content": list(content),
    }
