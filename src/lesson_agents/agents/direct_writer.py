from __future__ import annotations

from hashlib import sha256
import json

from lesson_agents.core.schemas import LessonDraft, LessonTask
from lesson_agents.models.base import ModelProvider, ModelResult
from lesson_agents.prompts import load_prompt


class DirectWriterAgent:
    prompt_version = "direct_writer_v1"
    temperature = 0.2

    def __init__(self, provider: ModelProvider) -> None:
        self._provider = provider
        self._system_prompt = load_prompt(f"{self.prompt_version}.txt")
        self.prompt_hash = sha256(self._system_prompt.encode("utf-8")).hexdigest()

    def run(
        self,
        *,
        task: LessonTask,
        knowledge: list[dict] | None = None,
    ) -> ModelResult[LessonDraft]:
        payload = {"task": task.model_dump(mode="json"), "knowledge": knowledge or []}
        return self._provider.generate_structured(
            system_prompt=self._system_prompt,
            user_prompt=json.dumps(payload, ensure_ascii=False, indent=2),
            schema=LessonDraft,
            temperature=self.temperature,
        )
