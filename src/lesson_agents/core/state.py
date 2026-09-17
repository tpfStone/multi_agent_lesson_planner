from __future__ import annotations

from typing import TypedDict


class LessonPlanState(TypedDict, total=False):
    """JSON-serializable state used by the active Phase 1 graph."""

    # Raw decoded JSON until Normalize succeeds, then a validated LessonTask dict.
    task: object
    outline: dict
    draft: dict
    formatted_plan: dict
    validation: dict
    current_stage: str
    errors: list[str]
    run_id: str
    status: str
