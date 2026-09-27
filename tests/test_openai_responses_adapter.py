from types import SimpleNamespace

from agentdojo.agent_pipeline.agent_pipeline import get_llm
from agentdojo.agent_pipeline.llms.anthropic_llm import AnthropicLLM
from agentdojo.agent_pipeline.llms.openai_llm import OpenAILLM
from agentdojo.agent_pipeline.llms.openai_responses_llm import (
    OpenAIResponsesLLM,
    _message_to_responses_input,
    _response_to_assistant_message,
)
from agentdojo.agent_pipeline.drift_defense.drift_client import (
    ModelCompletion,
    OpenAIModel,
    _messages_to_responses_input,
)
from agentdojo.functions_runtime import FunctionCall, FunctionsRuntime
from agentdojo.types import text_content_block_from_string


def _text(value: str):
    return [text_content_block_from_string(value)]


def test_converts_tool_round_trip_messages() -> None:
    call = FunctionCall(function="add", args={"a": 2, "b": 3}, id="call-1")

    assistant_items = _message_to_responses_input(
        {"role": "assistant", "content": _text("checking"), "tool_calls": [call]}
    )
    tool_items = _message_to_responses_input(
        {
            "role": "tool",
            "content": _text("5"),
            "tool_call": call,
            "tool_call_id": "call-1",
            "error": None,
        }
    )

    assert assistant_items == [
        {"type": "message", "role": "assistant", "content": "checking"},
        {
            "type": "function_call",
            "call_id": "call-1",
            "name": "add",
            "arguments": '{"a": 2, "b": 3}',
        },
    ]
    assert tool_items == [
        {"type": "function_call_output", "call_id": "call-1", "output": "5"}
    ]


def test_parses_text_and_function_call_response() -> None:
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="output_text", text="I will add them.")],
            ),
            SimpleNamespace(
                type="function_call",
                name="add",
                arguments='{"a": 2, "b": 3}',
                call_id="call-1",
            ),
        ]
    )

    message = _response_to_assistant_message(response)

    assert message["content"] == _text("I will add them.")
    assert message["tool_calls"] == [
        FunctionCall(function="add", args={"a": 2, "b": 3}, id="call-1")
    ]


def test_protocol_route_is_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "test-key")

    monkeypatch.delenv("OPENAI_COMPATIBLE_PROTOCOL", raising=False)
    assert isinstance(get_llm("model"), OpenAILLM)

    monkeypatch.setenv("OPENAI_COMPATIBLE_PROTOCOL", "responses")
    assert isinstance(get_llm("model"), OpenAIResponsesLLM)

    monkeypatch.setenv("OPENAI_COMPATIBLE_PROTOCOL", "anthropic_messages")
    assert isinstance(get_llm("model"), AnthropicLLM)


def test_query_records_usage() -> None:
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="output_text", text="done")],
            )
        ],
        usage=SimpleNamespace(input_tokens=11, output_tokens=3, total_tokens=14),
    )
    client = SimpleNamespace(
        responses=SimpleNamespace(create=lambda **kwargs: response)
    )
    llm = OpenAIResponsesLLM(client, "model", temperature=0.0)

    _, _, _, messages, extra_args = llm.query(
        "query",
        FunctionsRuntime(),
        messages=[{"role": "user", "content": _text("hello")}],
    )

    assert messages[-1]["content"] == _text("done")
    assert extra_args["openai_responses_usage"] == [
        {"input_tokens": 11, "output_tokens": 3, "total_tokens": 14}
    ]
    assert llm.usage_totals == {"input_tokens": 11, "output_tokens": 3, "total_tokens": 14}


def test_drift_converts_tool_observation_for_responses() -> None:
    assert _messages_to_responses_input(
        [
            {"role": "system", "content": "policy"},
            {"role": "tool", "content": "result"},
        ]
    ) == [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "Observation: result"},
    ]


def test_drift_uses_responses_protocol(monkeypatch) -> None:
    usage = SimpleNamespace(input_tokens=17, output_tokens=5, total_tokens=22)
    response = SimpleNamespace(output_text="defense output", usage=usage)
    calls = []
    model = OpenAIModel.__new__(OpenAIModel)
    model.model = "gpt-5.4-mini"
    model.max_completion_tokens = 100
    model.client = SimpleNamespace(
        responses=SimpleNamespace(create=lambda **kwargs: calls.append(kwargs) or response)
    )
    model.completion_tokens = 0
    model.prompt_tokens = 0
    model.total_tokens = 0
    model.tokens_dict = {
        "total_completion_tokens": 0,
        "total_prompt_tokens": 0,
        "total_total_tokens": 0,
    }
    monkeypatch.setenv("OPENAI_COMPATIBLE_PROTOCOL", "responses")

    result = model.agent_run(
        [
            {"role": "system", "content": "policy"},
            {"role": "user", "content": "task"},
        ],
        tools=[],
    )

    assert result == [ModelCompletion("defense output")]
    assert calls[0]["model"] == "gpt-5.4-mini"
    assert model.tokens_dict["total_total_tokens"] == 22
