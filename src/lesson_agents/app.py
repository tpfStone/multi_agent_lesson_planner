from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping
from uuid import uuid4

from pydantic import ValidationError

from lesson_agents import __version__
from lesson_agents.core.constants import PIPELINE_VERSIONS
from lesson_agents.core.schemas import LessonTask
from lesson_agents.core.state import LessonPlanState
from lesson_agents.graphs.phase1_pipeline import build_phase1_graph
from lesson_agents.graphs.direct_write_pipeline import build_direct_write_graph
from lesson_agents.knowledge.base import KnowledgeRetriever
from lesson_agents.knowledge.mock_retriever import MockRetriever
from lesson_agents.mock_scenario import build_mock_direct_write_provider, build_mock_phase1_provider
from lesson_agents.models.base import ModelProvider
from lesson_agents.models.mock import MockModelProvider
from lesson_agents.nodes.normalize import normalize_task_data
from lesson_agents.storage.artifact_store import ArtifactStore
from lesson_agents.storage.run_context import RunContext
from lesson_agents.storage.run_metadata import code_provenance, environment_versions, json_hash
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


def _default_mock_provider(
    raw_task: object, aliases: Mapping[str, str], pipeline: str,
) -> ModelProvider:
    if not isinstance(raw_task, Mapping):
        # Let Normalize reject non-object JSON after run records are initialized.
        return MockModelProvider()
    try:
        task = LessonTask.model_validate(normalize_task_data(raw_task, aliases))
    except ValidationError:
        # Normalize remains the authoritative graph node and will persist the real error.
        return MockModelProvider()
    if pipeline == "direct_write":
        return build_mock_direct_write_provider(task)
    return build_mock_phase1_provider(task)


def _run_metadata(
    *,
    run_id: str,
    provider: ModelProvider,
    context: RunContext,
    aliases: Mapping[str, str],
    pipeline: str,
    comparison_id: str | None,
    raw_input: object,
) -> dict[str, Any]:
    runtime = context.runtime_metadata
    agents_metadata = runtime.get("agents", {})
    return {
        "metadata_schema_version": 1,
        "run_id": run_id,
        "pipeline_id": pipeline,
        "pipeline_version": PIPELINE_VERSIONS[pipeline],
        "comparison_id": comparison_id,
        "input_hash": json_hash(raw_input),
        "normalized_task_hash": None,
        "hash_serialization": "SHA-256; decoded JSON; UTF-8; ensure_ascii=False; sort_keys=True; separators=(',', ':')",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "code_version": __version__,
        **code_provenance(),
        "environment": environment_versions(),
        "status": "running",
        "elapsed_ms": None,
        "timing_scope": (
            "perf_counter from validated pipeline selection, before provider/run initialization, "
            "through graph execution and failure handling; excludes the last run_meta write and return"
        ),
        "config_version": None,
        "provider": runtime.get("provider", provider.provider_name),
        "model_id": runtime.get("model_id", provider.model_id),
        "base_url": runtime.get("base_url", getattr(provider, "base_url", None)),
        "prompt_versions": {
            node: metadata["prompt_version"] for node, metadata in agents_metadata.items()
        },
        "prompt_hashes": {
            node: metadata["prompt_hash"] for node, metadata in agents_metadata.items()
        },
        "generation_parameters": {
            node: {"temperature": metadata["temperature"]}
            for node, metadata in agents_metadata.items()
        },
        "runtime_parameters": {"normalization_aliases": dict(aliases)},
        "knowledge": {
            node: {"status": "not_called", "request": None, "documents": None,
                   "snapshot_hash": None, "error": None}
            for node in runtime.get("knowledge_nodes", [])
        },
        "request_configuration": getattr(provider, "request_configuration", {
            "source": "provider_defined", "note": "Not exposed by this provider; unknown.",
        }),
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
    raw_task: object,
    *,
    provider: ModelProvider | None = None,
    retriever: KnowledgeRetriever | None = None,
    runs_dir: str | Path = "runs",
    aliases: Mapping[str, str] | None = None,
    pipeline: str = "outline_then_write",
    comparison_id: str | None = None,
) -> PipelineRunResult:
    """Execute A (default) or B for decoded JSON; Normalize validates the task object."""

    if pipeline not in PIPELINE_VERSIONS:
        raise ValueError(f"Unknown pipeline: {pipeline!r}; choose one of {tuple(PIPELINE_VERSIONS)}")
    started_clock = perf_counter()

    effective_aliases = dict(aliases or DEFAULT_ALIASES)
    effective_provider = provider or _default_mock_provider(raw_task, effective_aliases, pipeline)
    effective_retriever = retriever or MockRetriever()

    run_id = _new_run_id()
    runs_path = Path(runs_dir).resolve()
    runs_path.mkdir(parents=True, exist_ok=True)
    artifacts = ArtifactStore(runs_path / run_id)
    traces = TraceStore(run_id=run_id, path=artifacts.run_dir / "trace.jsonl")
    raw_input = dict(raw_task) if isinstance(raw_task, Mapping) else raw_task
    initial_state: LessonPlanState = {
        "task": raw_input,
        "run_id": run_id,
        "current_stage": "input_received",
        "errors": [],
        "status": "running",
    }
    context = RunContext(
        artifacts=artifacts, traces=traces, initial_state=initial_state, started_clock=started_clock,
    )

    def initialize_metadata() -> None:
        context.run_metadata = _run_metadata(
            run_id=run_id, provider=effective_provider, context=context,
            aliases=effective_aliases, pipeline=pipeline,
            comparison_id=comparison_id, raw_input=raw_input,
        )

    def record_pipeline_failure(node: str, error: Exception) -> None:
        span = traces.start_span(node=node, node_type="program_node")
        (artifacts.run_dir / "final.json").unlink(missing_ok=True)
        context.persist_failure(context.latest_state, node=node, error=error)
        span.finish(status="failed", artifact_path=None, error=str(error))

    artifacts.save_json("input.json", raw_input)
    try:
        builder = build_direct_write_graph if pipeline == "direct_write" else build_phase1_graph
        graph_builder = builder(
            provider=effective_provider,
            retriever=effective_retriever,
            context=context,
            aliases=effective_aliases,
        )
        initialize_metadata()
        context.persist_metadata()
        graph = graph_builder.compile()
        state = graph.invoke(initial_state)
        context.latest_state = state
    except Exception as exc:
        if context.run_metadata is None:
            initialize_metadata()
        if context.latest_state.get("status") != "failed" or not artifacts.exists("state.json"):
            record_pipeline_failure("pipeline", exc)

    # Completion metadata is required, including after a graph/node failure.
    # If a terminal write fails after Save, retract final and record that failure.
    try:
        context.finish_metadata()
    except Exception as exc:
        record_pipeline_failure("pipeline_metadata", exc)
        context.finish_metadata()
    state = context.latest_state

    final_path = artifacts.run_dir / "final.json"
    return PipelineRunResult(
        run_id=run_id,
        status=state.get("status", "failed"),
        state=state,
        run_dir=artifacts.run_dir,
        final_artifact_path=final_path if final_path.is_file() else None,
    )
