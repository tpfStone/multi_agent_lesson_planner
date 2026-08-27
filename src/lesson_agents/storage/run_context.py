from __future__ import annotations

from copy import deepcopy
from typing import Any

from lesson_agents.core.state import LessonPlanState
from lesson_agents.storage.artifact_store import ArtifactStore
from lesson_agents.storage.trace_store import TraceStore


class RunContext:
    """Tracks the latest committed State so failures can always be persisted."""

    def __init__(self, *, artifacts: ArtifactStore, traces: TraceStore, initial_state: LessonPlanState) -> None:
        self.artifacts = artifacts
        self.traces = traces
        self.latest_state: LessonPlanState = deepcopy(initial_state)
        self.runtime_metadata: dict[str, Any] = {}

    def capture(self, state: LessonPlanState, update: dict[str, Any]) -> LessonPlanState:
        merged: LessonPlanState = deepcopy(state)
        merged.update(deepcopy(update))
        self.latest_state = merged
        return merged

    def persist_failure(self, state: LessonPlanState, *, node: str, error: Exception | str) -> None:
        message = str(error)
        merged: LessonPlanState = deepcopy(self.latest_state)
        merged.update(deepcopy(state))
        errors = list(merged.get("errors", []))
        errors.append(f"{node}: {message}")
        merged.update(
            {
                "current_stage": node,
                "errors": errors,
                "status": "failed",
            }
        )
        self.latest_state = merged
        self.artifacts.save_json("state.json", merged)
