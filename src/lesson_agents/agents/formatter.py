from __future__ import annotations

import json
from hashlib import sha256

from lesson_agents.core.schemas import LessonDraft, LessonPlan, LessonTask
from lesson_agents.models.base import ModelProvider, ModelResult
from lesson_agents.prompts import load_prompt


class FormatterAgent:
    prompt_version = "formatter_v1"
    temperature = 0.0

    def __init__(self, provider: ModelProvider) -> None:
        self._provider = provider
        self._system_prompt = load_prompt(f"{self.prompt_version}.txt")
        self.prompt_hash = sha256(self._system_prompt.encode("utf-8")).hexdigest()

    def run(self, *, task: LessonTask, draft: LessonDraft) -> ModelResult[LessonPlan]:
        payload = {
            "task_metadata_to_preserve": task.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
        }
        return self._provider.generate_structured(
            system_prompt=self._system_prompt,
            user_prompt=json.dumps(payload, ensure_ascii=False, indent=2),
            schema=LessonPlan,
            temperature=self.temperature,
        )
