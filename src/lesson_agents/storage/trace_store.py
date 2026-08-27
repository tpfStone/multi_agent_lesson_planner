from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from lesson_agents.models.base import ModelMetadata


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TraceSpan:
    def __init__(
        self,
        *,
        store: "TraceStore",
        node: str,
        node_type: str,
        provider: str | None = None,
        model_id: str | None = None,
        prompt_version: str | None = None,
        temperature: float | None = None,
    ) -> None:
        self._store = store
        self._node = node
        self._node_type = node_type
        self._provider = provider
        self._model_id = model_id
        self._prompt_version = prompt_version
        self._temperature = temperature
        self._started_at = utc_now()
        self._started_clock = perf_counter()
        self._finished = False

    def finish(
        self,
        *,
        status: str,
        artifact_path: Path | None,
        metadata: ModelMetadata | None = None,
        error: str | None = None,
    ) -> None:
        if self._finished:
            raise RuntimeError("Trace span already finished")
        self._finished = True
        ended_at = utc_now()
        latency_ms = round((perf_counter() - self._started_clock) * 1000, 3)
        self._store.append(
            {
                "run_id": self._store.run_id,
                "node": self._node,
                "node_type": self._node_type,
                "status": status,
                "iteration": 0,
                "started_at": self._started_at,
                "ended_at": ended_at,
                "latency_ms": latency_ms,
                "artifact_path": self._store.artifact_reference(artifact_path),
                "provider": metadata.provider if metadata else self._provider,
                "model_id": metadata.model_id if metadata else self._model_id,
                "prompt_version": self._prompt_version,
                "temperature": metadata.temperature if metadata else self._temperature,
                "token_usage": metadata.token_usage if metadata else None,
                "error": error,
            }
        )


class TraceStore:
    def __init__(self, *, run_id: str, path: Path) -> None:
        self.run_id = run_id
        self.path = path.resolve()

    def start_span(
        self,
        *,
        node: str,
        node_type: str,
        provider: str | None = None,
        model_id: str | None = None,
        prompt_version: str | None = None,
        temperature: float | None = None,
    ) -> TraceSpan:
        return TraceSpan(
            store=self,
            node=node,
            node_type=node_type,
            provider=provider,
            model_id=model_id,
            prompt_version=prompt_version,
            temperature=temperature,
        )

    def artifact_reference(self, artifact_path: Path | None) -> str | None:
        """Return a run-relative reference and never expose a machine path."""

        if artifact_path is None:
            return None
        try:
            relative = artifact_path.resolve().relative_to(self.path.parent)
        except ValueError as exc:
            raise ValueError("Trace artifacts must be inside the current run directory") from exc
        return relative.as_posix()

    def append(self, event: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
