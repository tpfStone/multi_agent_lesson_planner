"""Phase 2 interface only; intentionally absent from the active Phase 1 graph."""

from __future__ import annotations

from typing import Protocol

from lesson_agents.core.schemas import EvaluationResult, LessonPlan


class Evaluator(Protocol):
    def evaluate(self, plan: LessonPlan) -> EvaluationResult: ...

