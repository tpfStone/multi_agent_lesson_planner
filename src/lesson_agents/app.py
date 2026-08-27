from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from pydantic import ValidationError

from lesson_agents import __version__
from lesson_agents.core.schemas import LessonTask
from lesson_agents.core.state import LessonPlanState
from lesson_agents.graphs.phase1_pipeline import build_phase1_graph
from lesson_agents.knowledge.base import KnowledgeRetriever
from lesson_agents.knowledge.mock_retriever import MockRetriever
from lesson_agents.mock_scenario import build_mock_phase1_provider
from lesson_agents.models.base import ModelProvider
from lesson_agents.models.mock import MockModelProvider
from lesson_agents.nodes.normalize import normalize_task_data
from lesson_agents.storage.artifact_store import ArtifactStore
from lesson_agents.storage.run_context import RunContext
from lesson_agents.storage.trace_store import TraceStore

DEFAULT_ALIASES = {
    "subject_name": "subject",
    "grade_level": "grade",
    "lesson_topic": "topic",
}


@dataclass(frozen=True, slots=True)
class PipelineRunResult:
    run_id: str
    status: str
    state: LessonPlanState
    run_dir: Path
    final_artifact_path: Path | None

    @property
    def validation_valid(self) -> bool:
        return self.state.get("validation", {}).get("valid") is True


def _new_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid4().hex[:8]}"


def _default_mock_provider(raw_task: Mapping[str, Any], aliases: Mapping[str, str]) -> ModelProvider:
    try:
        task = LessonTask.model_validate(normalize_task_data(raw_task, aliases))
    except ValidationError:
        # Normalize remains the authoritative graph node and will persist the real error.
        return MockModelProvider()
    return build_mock_phase1_provider(task)


def _run_metadata(
    *,
    run_id: str,
    provider: ModelProvider,
    context: RunContext,
    aliases: Mapping[str, str],
) -> dict[str, Any]:
    runtime = context.runtime_metadata
    agents_metadata = runtime.get("agents", {})
    return {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "code_version": __version__,
        "git_commit": None,
        "config_version": None,
        "provider": runtime.get("provider", provider.provider_name),
        "model_id": runtime.get("model_id", provider.model_id),
        "base_url": runtime.get("base_url", getattr(provider, "base_url", None)),
        "prompt_versions": {
            node: metadata["prompt_version"] for node, metadata in agents_metadata.items()
        },
        "generation_parameters": {
            node: {"temperature": metadata["temperature"]}
            for node, metadata in agents_metadata.items()
        },
        "runtime_parameters": {"normalization_aliases": dict(aliases)},
        "configuration": {
            "provider_configuration_source": runtime.get(
                "provider_configuration_source",
                getattr(provider, "configuration_source", "unknown"),
            ),
            "config_files_loaded": [],
            "dotenv_loaded": "dotenv" in runtime.get(
                "provider_configuration_source",
                getattr(provider, "configuration_source", "unknown"),
            ),
            "note": (
                "config/*.yaml are reference/reserved files in Phase 1 and are not "
                "loaded by the runtime; examples/04_lesson_pipeline.py explicitly loads "
                ".env only for --real, then OpenAIModelProvider reads environment variables."
            ),
        },
    }


def run_lesson_pipeline(
    raw_task: Mapping[str, Any],
    *,
    provider: ModelProvider | None = None,
    retriever: KnowledgeRetriever | None = None,
    runs_dir: str | Path = "runs",
    aliases: Mapping[str, str] | None = None,
) -> PipelineRunResult:
    """Execute the Phase 1 graph and always return a persisted run result."""

    effective_aliases = dict(aliases or DEFAULT_ALIASES)
    effective_provider = provider or _default_mock_provider(raw_task, effective_aliases)
    effective_retriever = retriever or MockRetriever()

    run_id = _new_run_id()
    runs_path = Path(runs_dir).resolve()
    runs_path.mkdir(parents=True, exist_ok=True)
    artifacts = ArtifactStore(runs_path / run_id)
    traces = TraceStore(run_id=run_id, path=artifacts.run_dir / "trace.jsonl")
    initial_state: LessonPlanState = {
        "task": dict(raw_task),
        "run_id": run_id,
        "current_stage": "input_received",
        "errors": [],
        "status": "running",
    }
    context = RunContext(artifacts=artifacts, traces=traces, initial_state=initial_state)

    artifacts.save_json("input.json", dict(raw_task))
    try:
        graph_builder = build_phase1_graph(
            provider=effective_provider,
            retriever=effective_retriever,
            context=context,
            aliases=effective_aliases,
        )
        artifacts.save_json(
            "run_meta.json",
            _run_metadata(
                run_id=run_id,
                provider=effective_provider,
                context=context,
                aliases=effective_aliases,
            ),
        )
        graph = graph_builder.compile()
        state = graph.invoke(initial_state)
        context.latest_state = state
    except Exception as exc:
        if not artifacts.exists("run_meta.json"):
            artifacts.save_json(
                "run_meta.json",
                _run_metadata(
                    run_id=run_id,
                    provider=effective_provider,
                    context=context,
                    aliases=effective_aliases,
                ),
            )
        if not artifacts.exists("state.json"):
            context.persist_failure(context.latest_state, node="pipeline", error=exc)
        state = context.latest_state

    final_path = artifacts.run_dir / "final.json"
    return PipelineRunResult(
        run_id=run_id,
        status=state.get("status", "failed"),
        state=state,
        run_dir=artifacts.run_dir,
        final_artifact_path=final_path if final_path.is_file() else None,
    )
