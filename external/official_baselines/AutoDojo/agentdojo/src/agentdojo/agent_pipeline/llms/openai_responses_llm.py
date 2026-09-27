import json
from collections.abc import Sequence
from typing import Any

import openai
from openai._types import NOT_GIVEN
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_random_exponential

from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.functions_runtime import EmptyEnv, Env, Function, FunctionCall, FunctionsRuntime
from agentdojo.types import (
    ChatAssistantMessage,
    ChatMessage,
    MessageContentBlock,
    get_text_content_as_str,
    text_content_block_from_string,
)


def _message_to_responses_input(message: ChatMessage) -> list[dict[str, Any]]:
    """Convert one AgentDojo message into stateless Responses API input items."""
    match message["role"]:
        case "system" | "user":
            return [
                {
                    "type": "message",
                    "role": message["role"],
                    "content": get_text_content_as_str(message["content"]),
                }
            ]
        case "assistant":
            items: list[dict[str, Any]] = []
            if message["content"]:
                items.append(
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": get_text_content_as_str(message["content"]),
                    }
                )
            for tool_call in message["tool_calls"] or []:
                if tool_call.id is None:
                    raise ValueError("`tool_call.id` is required for the Responses API")
                items.append(
                    {
                        "type": "function_call",
                        "call_id": tool_call.id,
                        "name": tool_call.function,
                        "arguments": json.dumps(tool_call.args),
                    }
                )
            return items
        case "tool":
            if message["tool_call_id"] is None:
                raise ValueError("`tool_call_id` is required for the Responses API")
            output = message["error"] or get_text_content_as_str(message["content"])
            return [
                {
                    "type": "function_call_output",
                    "call_id": message["tool_call_id"],
                    "output": output,
                }
            ]
        case _:
            raise ValueError(f"Invalid message type: {message}")


def _function_to_responses_tool(function: Function) -> dict[str, Any]:
    return {
        "type": "function",
        "name": function.name,
        "description": function.description,
        "parameters": function.parameters.model_json_schema(),
        "strict": False,
    }


def _decode_arguments(arguments: str) -> dict[str, Any]:
    args = json.loads(arguments)
    if isinstance(args, str):
        args = json.loads(args)
    if not isinstance(args, dict):
        raise ValueError(f"Function arguments must decode to an object, got {type(args).__name__}")
    return args


def _response_to_assistant_message(response: Any) -> ChatAssistantMessage:
    content: list[MessageContentBlock] = []
    tool_calls: list[FunctionCall] = []

    for item in response.output:
        item_type = getattr(item, "type", None)
        if item_type == "message":
            for block in item.content:
                if getattr(block, "type", None) == "output_text":
                    content.append(text_content_block_from_string(block.text))
                elif getattr(block, "type", None) == "refusal":
                    content.append(text_content_block_from_string(block.refusal))
        elif item_type == "function_call":
            tool_calls.append(
                FunctionCall(
                    function=item.name,
                    args=_decode_arguments(item.arguments),
                    id=item.call_id,
                )
            )

    return ChatAssistantMessage(
        role="assistant",
        content=content or None,
        tool_calls=tool_calls or None,
    )


@retry(
    wait=wait_random_exponential(multiplier=1, max=40),
    stop=stop_after_attempt(3),
    reraise=True,
    retry=retry_if_not_exception_type((openai.BadRequestError, openai.UnprocessableEntityError)),
)
def responses_request(
    client: openai.OpenAI,
    model: str,
    inputs: Sequence[dict[str, Any]],
    tools: Sequence[dict[str, Any]],
    temperature: float | None,
) -> Any:
    return client.responses.create(
        model=model,
        input=inputs,
        tools=tools or NOT_GIVEN,
        tool_choice="auto" if tools else NOT_GIVEN,
        temperature=temperature if temperature is not None else NOT_GIVEN,
    )


class OpenAIResponsesLLM(BasePipelineElement):
    """OpenAI-compatible LLM adapter for models exposed only via Responses API."""

    def __init__(
        self,
        client: openai.OpenAI,
        model: str,
        temperature: float | None = 0.0,
    ) -> None:
        self.client = client
        self.model = model
        self.temperature = temperature
        self.usage_totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),
        messages: Sequence[ChatMessage] = [],
        extra_args: dict = {},
    ) -> tuple[str, FunctionsRuntime, Env, Sequence[ChatMessage], dict]:
        response_inputs = [
            item for message in messages for item in _message_to_responses_input(message)
        ]
        response_tools = [_function_to_responses_tool(tool) for tool in runtime.functions.values()]
        response = responses_request(
            self.client,
            self.model,
            response_inputs,
            response_tools,
            self.temperature,
        )
        output = _response_to_assistant_message(response)

        if response.usage is not None:
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            for key, value in usage.items():
                self.usage_totals[key] += value
            extra_args = dict(extra_args)
            extra_args.setdefault("openai_responses_usage", []).append(usage)

        return query, runtime, env, [*messages, output], extra_args
