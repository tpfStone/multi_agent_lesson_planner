from __future__ import annotations

import json

from lesson_agents.core.schemas import LessonOutline, LessonTask
from lesson_agents.models.base import ModelProvider, ModelResult
from lesson_agents.prompts import load_prompt


class OutlinePlannerAgent:
    prompt_version = "outline_planner_v1"
    temperature = 0.2

    def __init__(self, provider: ModelProvider) -> None:
        self._provider = provider
        self._system_prompt = load_prompt(f"{self.prompt_version}.txt")

    def run(
        self,
        *,
        task: LessonTask,
        knowledge: list[dict] | None = None,
    ) -> ModelResult[LessonOutline]:
        payload = {"task": task.model_dump(mode="json"), "knowledge": knowledge or []}
        return self._provider.generate_structured(
            system_prompt=self._system_prompt,
            user_prompt=json.dumps(payload, ensure_ascii=False, indent=2),
            schema=LessonOutline,
            temperature=self.temperature,
        )

