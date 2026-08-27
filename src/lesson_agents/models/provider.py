from __future__ import annotations

import json
import os
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

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

_API_KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_*\-]{6,}\b")


def _safe_provider_error(exc: Exception) -> str:
    """Remove API-key-like fragments before errors reach State or trace."""

    return _API_KEY_PATTERN.sub("[REDACTED_API_KEY]", str(exc))


class OpenAIModelProvider:
    """The single primary real-provider adapter implemented for Phase 1.

    Prompts, roles, and lesson logic remain in Agent classes. The client can be
    injected so adapter behavior is testable without a network call.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model_id: str,
        client: Any | None = None,
        configuration_source: str = "constructor_arguments",
    ) -> None:
        if not api_key:
            raise ModelProviderError("OPENAI_API_KEY is required for the real provider")
        if not model_id:
            raise ModelProviderError("LESSON_MODEL_ID is required for the real provider")
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ModelProviderError(
                    "Install the real-provider extra with: pip install -e '.[real]'"
                ) from exc
            client = OpenAI(api_key=api_key)
        self._client = client
        self._model_id = model_id
        self._configuration_source = configuration_source
        client_base_url = getattr(client, "base_url", None)
        self._base_url = str(client_base_url) if client_base_url is not None else None

    @classmethod
    def from_env(
        cls,
        *,
        client: Any | None = None,
        configuration_source: str = "environment",
    ) -> "OpenAIModelProvider":
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model_id=os.getenv("LESSON_MODEL_ID", ""),
            client=client,
            configuration_source=configuration_source,
        )

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def configuration_source(self) -> str:
        return self._configuration_source

    @property
    def base_url(self) -> str | None:
        return self._base_url

    @staticmethod
    def _usage(response: Any) -> dict[str, int] | None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return None
        raw = usage.model_dump() if hasattr(usage, "model_dump") else vars(usage)
        result = {
            key: value
            for key, value in raw.items()
            if isinstance(value, int) and key in {"prompt_tokens", "completion_tokens", "total_tokens"}
        }
        return result or None

    def _metadata(self, response: Any, temperature: float | None) -> ModelMetadata:
        return ModelMetadata(
            provider=self.provider_name,
            model_id=self.model_id,
            temperature=temperature,
            token_usage=self._usage(response),
        )

    def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
    ) -> TextModelResult:
        try:
            response = self._client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )
            content = response.choices[0].message.content
            if not isinstance(content, str) or not content.strip():
                raise ModelProviderError("Real provider returned an empty text response")
            return TextModelResult(value=content, metadata=self._metadata(response, temperature))
        except ModelProviderError:
            raise
        except Exception as exc:
            raise ModelProviderError(f"Real text generation failed: {_safe_provider_error(exc)}") from exc

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
        temperature: float | None = None,
    ) -> ModelResult[T]:
        try:
            response = self._client.chat.completions.parse(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=schema,
                temperature=temperature,
            )
            parsed = response.choices[0].message.parsed
            if parsed is None:
                raise ModelProviderError("Real provider returned no parsed structured output")
            value = parsed if isinstance(parsed, schema) else schema.model_validate(parsed)
            return ModelResult(value=value, metadata=self._metadata(response, temperature))
        except ModelProviderError:
            raise
        except Exception as exc:
            raise ModelProviderError(
                f"Real structured generation failed: {_safe_provider_error(exc)}"
            ) from exc

    def generate_tool_call(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[ToolDefinition],
        temperature: float | None = None,
    ) -> ToolCallResult:
        tool_payload = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                    "strict": True,
                },
            }
            for tool in tools
        ]
        try:
            response = self._client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                tools=tool_payload,
                tool_choice="required",
                temperature=temperature,
            )
            tool_calls = response.choices[0].message.tool_calls or []
            if len(tool_calls) != 1:
                raise ModelProviderError("Real provider must return exactly one tool call")
            function = tool_calls[0].function
            arguments = json.loads(function.arguments)
            if not isinstance(arguments, dict):
                raise ModelProviderError("Tool arguments must decode to a JSON object")
            call = ToolCall(name=function.name, arguments=arguments)
            return ToolCallResult(value=call, metadata=self._metadata(response, temperature))
        except (json.JSONDecodeError, TypeError) as exc:
            raise ModelProviderError(
                f"Real provider returned invalid tool arguments: {_safe_provider_error(exc)}"
            ) from exc
        except ModelProviderError:
            raise
        except Exception as exc:
            raise ModelProviderError(f"Real tool selection failed: {_safe_provider_error(exc)}") from exc


class DeepSeekModelProvider(OpenAIModelProvider):
    """DeepSeek's OpenAI-compatible API with JSON Output + Pydantic validation."""

    default_base_url = "https://api.deepseek.com"

    def __init__(
        self,
        *,
        api_key: str,
        model_id: str,
        client: Any | None = None,
        configuration_source: str = "constructor_arguments",
    ) -> None:
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ModelProviderError(
                    "Install the real-provider extra with: pip install -e '.[real]'"
                ) from exc
            client = OpenAI(api_key=api_key, base_url=self.default_base_url)
        super().__init__(
            api_key=api_key,
            model_id=model_id,
            client=client,
            configuration_source=configuration_source,
        )
        self._base_url = self.default_base_url

    @classmethod
    def from_env(
        cls,
        *,
        client: Any | None = None,
        configuration_source: str = "environment",
    ) -> "DeepSeekModelProvider":
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        return cls(
            api_key=api_key,
            model_id=os.getenv("LESSON_MODEL_ID", ""),
            client=client,
            configuration_source=configuration_source,
        )

    @property
    def provider_name(self) -> str:
        return "deepseek"

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
        temperature: float | None = None,
    ) -> ModelResult[T]:
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        adapted_system_prompt = (
            f"{system_prompt}\n\n"
            "Return only one valid JSON object. Do not use Markdown fences or add commentary. "
            "The JSON object must conform exactly to the supplied JSON Schema."
        )
        adapted_user_prompt = f"{user_prompt}\n\nJSON Schema:\n{schema_json}"
        try:
            response = self._client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": adapted_system_prompt},
                    {"role": "user", "content": adapted_user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
            )
        except Exception as exc:
            raise ModelProviderError(
                f"DeepSeek API request failed: {_safe_provider_error(exc)}"
            ) from exc

        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise ModelProviderError("DeepSeek API returned empty JSON content")
        try:
            value = schema.model_validate_json(content)
        except ValidationError as exc:
            raise ModelProviderError(
                f"DeepSeek structured response failed Pydantic validation: {exc}"
            ) from exc
        return ModelResult(value=value, metadata=self._metadata(response, temperature))
