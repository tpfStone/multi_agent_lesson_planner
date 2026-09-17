from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from lesson_agents.core.schemas import LessonTask
from lesson_agents.core.state import LessonPlanState
from lesson_agents.storage.run_context import RunContext


def normalize_task_data(raw_task: Mapping[str, Any], aliases: Mapping[str, str] | None = None) -> dict:
    """Apply only explicit aliases and safe whitespace normalization."""

    normalized = deepcopy(dict(raw_task))
    for alias, canonical in (aliases or {}).items():
        if alias in normalized and canonical not in normalized:
            normalized[canonical] = normalized[alias]
        normalized.pop(alias, None)

    for key in ("task_id", "subject", "grade", "topic", "duration", "language"):
        value = normalized.get(key)
        if isinstance(value, str):
            normalized[key] = value.strip()

    requirements = normalized.get("requirements")
    if isinstance(requirements, list):
        normalized["requirements"] = [
            item.strip() if isinstance(item, str) else item for item in requirements
        ]
    if normalized.get("duration") == "":
        normalized["duration"] = None
    return normalized


def make_normalize_node(
    context: RunContext,
    *,
    aliases: Mapping[str, str] | None = None,
):
    def normalize_input(state: LessonPlanState) -> dict:
        span = context.traces.start_span(node="normalize_input", node_type="program_node")
        try:
            raw_task = state.get("task")
            if not isinstance(raw_task, Mapping):
                raise ValueError("State.task must be a JSON object")
            task = LessonTask.model_validate(normalize_task_data(raw_task, aliases))
            update = {
                "task": task.model_dump(mode="json"),
                "current_stage": "normalized",
                "errors": list(state.get("errors", [])),
                "status": "running",
            }
            artifact = context.artifacts.save_json("01_normalized.json", update["task"])
            context.capture(state, update)
            context.record_normalized_task(update["task"])
            span.finish(status="success", artifact_path=artifact)
            return update
        except Exception as exc:
            span.finish(status="failed", artifact_path=None, error=str(exc))
            context.persist_failure(state, node="normalize_input", error=exc)
            raise

    return normalize_input
