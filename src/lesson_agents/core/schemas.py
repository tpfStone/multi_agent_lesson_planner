from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LessonTask(StrictSchema):
    task_id: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    grade: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    duration: str | None = None
    requirements: list[str] = Field(default_factory=list)
    language: str = "zh-CN"


class TeachingObjective(StrictSchema):
    category: str = Field(min_length=1)
    content: str = Field(min_length=1)


class LessonStage(StrictSchema):
    name: str = Field(min_length=1)
    duration_minutes: int | None = None
    goal: str = Field(min_length=1)
    teacher_activity: str | None = None
    student_activity: str | None = None
    assessment: str | None = None


class DetailedLessonStage(LessonStage):
    """A fully written stage required in Writer and Formatter outputs."""

    teacher_activity: NonEmptyText
    student_activity: NonEmptyText
    assessment: NonEmptyText


class LessonOutline(StrictSchema):
    teaching_objectives: list[TeachingObjective]
    key_points: list[str]
    difficult_points: list[str]
    stages: list[LessonStage]
    strategy_notes: list[str]


class LessonDraft(StrictSchema):
    title: str = Field(min_length=1)
    overview: str = Field(min_length=1)
    objectives: list[TeachingObjective]
    key_points: list[str]
    difficult_points: list[str]
    stages: list[DetailedLessonStage]
    homework: list[str]
    notes: list[str]


class LessonPlan(StrictSchema):
    task: LessonTask
    title: str = Field(min_length=1)
    overview: str = Field(min_length=1)
    objectives: list[TeachingObjective]
    key_points: list[str]
    difficult_points: list[str]
    stages: list[DetailedLessonStage]
    assessment: list[str]
    homework: list[str]
    notes: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)


class ValidationResult(StrictSchema):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# Phase 2 contracts only. They are deliberately unused by the Phase 1 graph.
class EvaluationResult(StrictSchema):
    completeness_score: float
    clarity_score: float
    teaching_logic_score: float
    overall_score: float
    failed_dimensions: list[str]
    strengths: list[str]
    problems: list[str]
    pass_recommended: bool


class CritiqueResult(StrictSchema):
    root_causes: list[str]
    revision_suggestions: list[str]
    priority_actions: list[str]


class SubtaskPlan(StrictSchema):
    id: str
    role: str
    instruction: str
    dependencies: list[str] = Field(default_factory=list)
    expected_output: str
