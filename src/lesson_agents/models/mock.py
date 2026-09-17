from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel

from lesson_agents.core.exceptions import ModelProviderError
from lesson_agents.models.base import (
    ModelMetadata,
    ModelResult,
    TextModelResult,
    ToolCall,
    ToolCallResult,
    ToolDefinition,
)

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class ScriptedStructuredResponse:
    schema_name: str
    value: dict[str, Any]


class MockModelProvider:
    """Network-free provider that replays deterministic scripted responses.

    Domain-specific lesson content is supplied by fixtures outside the provider,
    keeping this adapter responsible only for model-call behavior.
    """

    def __init__(
        self,
        *,
        text_responses: list[str] | None = None,
        structured_responses: list[ScriptedStructuredResponse] | None = None,
        tool_calls: list[ToolCall] | None = None,
        model_id: str = "deterministic-script-v1",
    ) -> None:
        self._text_responses = deque(text_responses or [])
        self._structured_responses = deque(structured_responses or [])
        self._tool_calls = deque(tool_calls or [])
        self._model_id = model_id
        self.call_log: list[dict[str, Any]] = []

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def configuration_source(self) -> str:
        return "scripted_arguments"

    @property
    def request_configuration(self) -> dict:
        return {"source": "scripted_arguments", "network_requests": False,
                "timeout": None, "max_retries": None, "output_token_limit": None}

    def _metadata(self, temperature: float | None) -> ModelMetadata:
        return ModelMetadata(
            provider=self.provider_name,
            model_id=self.model_id,
            temperature=temperature,
            token_usage=None,
        )

    def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
    ) -> TextModelResult:
        self.call_log.append({"kind": "text", "system": system_prompt, "user": user_prompt})
        if not self._text_responses:
            raise ModelProviderError("MockModelProvider has no scripted text response remaining")
        return TextModelResult(
            value=self._text_responses.popleft(),
            metadata=self._metadata(temperature),
        )

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
        temperature: float | None = None,
    ) -> ModelResult[T]:
        self.call_log.append(
            {"kind": "structured", "system": system_prompt, "user": user_prompt, "schema": schema.__name__}
        )
        if not self._structured_responses:
            raise ModelProviderError("MockModelProvider has no scripted structured response remaining")
        scripted = self._structured_responses.popleft()
        if scripted.schema_name != schema.__name__:
            raise ModelProviderError(
                f"Expected scripted schema {scripted.schema_name}, received {schema.__name__}"
            )
        return ModelResult(
            value=schema.model_validate(scripted.value),
            metadata=self._metadata(temperature),
        )

    def generate_tool_call(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[ToolDefinition],
        temperature: float | None = None,
    ) -> ToolCallResult:
        self.call_log.append(
            {
                "kind": "tool_call",
                "system": system_prompt,
                "user": user_prompt,
                "tools": [tool.name for tool in tools],
            }
        )
        if not self._tool_calls:
            raise ModelProviderError("MockModelProvider has no scripted tool call remaining")
        call = self._tool_calls.popleft()
        available = {tool.name for tool in tools}
        if call.name not in available:
            raise ModelProviderError(f"Mock requested unavailable tool: {call.name}")
        return ToolCallResult(value=call, metadata=self._metadata(temperature))
