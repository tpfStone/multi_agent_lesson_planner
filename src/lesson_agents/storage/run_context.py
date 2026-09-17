from __future__ import annotations

from copy import deepcopy
from time import perf_counter
from typing import Any

from lesson_agents.core.schemas import LessonTask
from lesson_agents.core.state import LessonPlanState
from lesson_agents.knowledge.base import KnowledgeRetriever
from lesson_agents.storage.artifact_store import ArtifactStore
from lesson_agents.storage.run_metadata import json_hash
from lesson_agents.storage.trace_store import TraceStore


class RunContext:
    """Tracks the latest committed State so failures can always be persisted."""

    def __init__(
        self, *, artifacts: ArtifactStore, traces: TraceStore,
        initial_state: LessonPlanState, started_clock: float | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.traces = traces
        self.latest_state: LessonPlanState = deepcopy(initial_state)
        self.runtime_metadata: dict[str, Any] = {}
        self.run_metadata: dict[str, Any] | None = None
        self.started_clock = perf_counter() if started_clock is None else started_clock

    def persist_metadata(self) -> None:
        if self.run_metadata is not None:
            self.artifacts.save_json("run_meta.json", self.run_metadata)

    def record_normalized_task(self, task: dict) -> None:
        if self.run_metadata is not None:
            self.run_metadata["normalized_task_hash"] = json_hash(task)
            self.persist_metadata()

    def retrieve_knowledge(
        self, *, node: str, retriever: KnowledgeRetriever, task: LessonTask, query: str,
    ) -> list[dict]:
        request = {
            "subject": task.subject, "grade": task.grade,
            "topic": task.topic, "query": query,
        }
        record = {"status": "failed", "request": request, "documents": None,
                  "snapshot_hash": None, "error": None}
        if self.run_metadata is not None:
            self.run_metadata["knowledge"][node] = record
        try:
            documents = retriever.retrieve(**request)
            record.update(status="retrieved", documents=deepcopy(documents),
                          snapshot_hash=json_hash(documents))
        except Exception as exc:
            record["status"] = "failed"
            record["error"] = str(exc)
            self.persist_metadata()
            raise
        # Persist the actual snapshot before any model call, including empty lists.
        self.persist_metadata()
        return documents

    def finish_metadata(self) -> None:
        if self.run_metadata is not None:
            self.run_metadata.update(
                status=self.latest_state.get("status", "failed"),
                elapsed_ms=round((perf_counter() - self.started_clock) * 1000, 3),
            )
            self.persist_metadata()

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
