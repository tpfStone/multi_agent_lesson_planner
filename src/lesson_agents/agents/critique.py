"""Phase 2 interface only; intentionally absent from the active Phase 1 graph."""

from __future__ import annotations

from typing import Protocol

from lesson_agents.core.schemas import CritiqueResult, EvaluationResult, LessonPlan


class Critique(Protocol):
    def critique(self, plan: LessonPlan, evaluation: EvaluationResult) -> CritiqueResult: ...

