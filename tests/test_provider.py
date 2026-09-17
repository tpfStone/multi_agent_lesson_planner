from types import SimpleNamespace
import sys

import pytest

from lesson_agents.core.exceptions import ModelProviderError
from lesson_agents.core.schemas import LessonTask
from lesson_agents.models.base import ToolDefinition
from lesson_agents.models.provider import DeepSeekModelProvider, OpenAIModelProvider


class FakeUsage:
    def model_dump(self):
        return {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


class FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(("create", kwargs))
        if "tools" in kwargs:
            function = SimpleNamespace(
                name="calculator",
                arguments='{"operation":"add","left":2,"right":3}',
            )
            message = SimpleNamespace(content=None, tool_calls=[SimpleNamespace(function=function)])
        else:
            message = SimpleNamespace(content="text response", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=FakeUsage())

    def parse(self, **kwargs):
        self.calls.append(("parse", kwargs))
        parsed = LessonTask(task_id="x", subject="数学", grade="七年级", topic="方程")
        message = SimpleNamespace(parsed=parsed)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=FakeUsage())


class FailingCompletions:
    def parse(self, **kwargs):
        del kwargs
        raise RuntimeError("Incorrect API key provided: sk-abc123********xyz789")


class FakeDeepSeekCompletions:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=FakeUsage())


def _provider():
    completions = FakeCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return OpenAIModelProvider(api_key="not-used", model_id="test-model", client=client), completions


def test_real_provider_requires_explicit_credentials() -> None:
    with pytest.raises(ModelProviderError):
        OpenAIModelProvider(api_key="", model_id="test-model", client=object())
    with pytest.raises(ModelProviderError):
        OpenAIModelProvider(api_key="not-used", model_id="", client=object())


def test_real_provider_from_env_records_configuration_source(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "not-used")
    monkeypatch.setenv("LESSON_MODEL_ID", "test-model")

    provider = OpenAIModelProvider.from_env(
        client=object(),
        configuration_source="dotenv",
    )

    assert provider.model_id == "test-model"
    assert provider.configuration_source == "dotenv"


def test_real_provider_adapter_parses_structured_output_without_network() -> None:
    provider, completions = _provider()

    response = provider.generate_structured(
        system_prompt="role",
        user_prompt="task",
        schema=LessonTask,
        temperature=0.2,
    )

    assert response.value.task_id == "x"
    assert response.metadata.token_usage == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }
    assert completions.calls[0][0] == "parse"


def test_real_provider_adapter_exposes_native_tool_call_without_network() -> None:
    provider, completions = _provider()
    tool = ToolDefinition(
        name="calculator",
        description="calculate",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
    )

    response = provider.generate_tool_call(
        system_prompt="role",
        user_prompt="2+3",
        tools=[tool],
        temperature=0.0,
    )

    assert response.value.name == "calculator"
    assert response.value.arguments["operation"] == "add"
    assert completions.calls[0][1]["tool_choice"] == "required"


def test_real_provider_redacts_api_key_fragments_from_errors() -> None:
    client = SimpleNamespace(chat=SimpleNamespace(completions=FailingCompletions()))
    provider = OpenAIModelProvider(api_key="not-used", model_id="test-model", client=client)

    with pytest.raises(ModelProviderError) as captured:
        provider.generate_structured(
            system_prompt="role",
            user_prompt="task",
            schema=LessonTask,
        )

    message = str(captured.value)
    assert "[REDACTED_API_KEY]" in message
    assert "sk-" not in message


def test_deepseek_provider_uses_json_output_then_pydantic_validation() -> None:
    content = '{"task_id":"x","subject":"数学","grade":"七年级","topic":"方程"}'
    completions = FakeDeepSeekCompletions(content)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = DeepSeekModelProvider(
        api_key="not-used",
        model_id="deepseek-v4-flash",
        client=client,
    )

    response = provider.generate_structured(
        system_prompt="role",
        user_prompt="task",
        schema=LessonTask,
        temperature=0.2,
    )

    assert response.value.task_id == "x"
    assert response.metadata.provider == "deepseek"
    assert completions.calls[0]["response_format"] == {"type": "json_object"}
    assert "JSON Schema" in completions.calls[0]["messages"][1]["content"]


def test_deepseek_provider_does_not_relax_pydantic_schema() -> None:
    completions = FakeDeepSeekCompletions('{"task_id":"x"}')
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = DeepSeekModelProvider(
        api_key="not-used",
        model_id="deepseek-v4-flash",
        client=client,
    )

    with pytest.raises(ModelProviderError, match="Pydantic validation"):
        provider.generate_structured(
            system_prompt="role",
            user_prompt="task",
            schema=LessonTask,
        )


@pytest.mark.parametrize("provider_class", [OpenAIModelProvider, DeepSeekModelProvider])
def test_request_configuration_distinguishes_injected_clients_and_sdk_defaults(monkeypatch, provider_class):
    calls = []

    def fake_client(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(base_url=kwargs.get("base_url"))

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=fake_client))
    default = provider_class(api_key="not-used", model_id="test-model")
    injected = provider_class(api_key="not-used", model_id="test-model", client=object())
    assert len(calls) == 1
    assert not {"timeout", "max_retries", "max_tokens"} & calls[0].keys()
    assert default.request_configuration["source"] == "sdk_defaults"
    assert injected.request_configuration["source"] == "injected_client_configuration"
    assert default.request_configuration["output_token_limit"]["explicit_in_adapter"] is False
