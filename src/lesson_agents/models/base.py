from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    provider: str
    model_id: str
    temperature: float | None = None
    token_usage: dict[str, int] | None = None


@dataclass(frozen=True, slots=True)
class ModelResult(Generic[T]):
    value: T
    metadata: ModelMetadata


@dataclass(frozen=True, slots=True)
class TextModelResult:
    value: str
    metadata: ModelMetadata


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolCallResult:
    value: ToolCall
    metadata: ModelMetadata


class ModelProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def model_id(self) -> str: ...

    def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
    ) -> TextModelResult: ...

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
        temperature: float | None = None,
    ) -> ModelResult[T]: ...

    def generate_tool_call(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[ToolDefinition],
        temperature: float | None = None,
    ) -> ToolCallResult: ...

