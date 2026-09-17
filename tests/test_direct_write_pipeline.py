"""Candidate B acceptance: independent execution, unchanged A, and durable failures."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import pytest

from lesson_agents.app import run_lesson_pipeline
from lesson_agents.core.constants import DIRECT_WRITE_NODE_ORDER, PHASE1_NODE_ORDER
from lesson_agents.core.exceptions import ModelProviderError
from lesson_agents.core.schemas import LessonDraft, LessonPlan, LessonTask
from lesson_agents.mock_scenario import build_mock_direct_write_provider, build_mock_phase1_provider
from lesson_agents.models.mock import MockModelProvider
from lesson_agents.nodes.schema_validate import validate_formatted_plan
from lesson_agents.storage.artifact_store import ArtifactStore
from lesson_agents.storage import run_metadata
from lesson_agents.storage.trace_store import TraceStore


ROOT = Path(__file__).resolve().parents[1]
TASK = json.loads((ROOT / "data/inputs/math_001.json").read_text(encoding="utf-8"))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def trace(result):
    return [json.loads(line) for line in (result.run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()]


def run_b(tmp_path, raw=TASK, **kwargs):
    return run_lesson_pipeline(raw, pipeline="direct_write", runs_dir=tmp_path, **kwargs)


def assert_failed(result, nodes):
    assert result.status == "failed"
    assert result.final_artifact_path is None
    assert not (result.run_dir / "final.json").exists()
    assert result.state == read_json(result.run_dir / "state.json")
    assert result.state["errors"]
    events = trace(result)
    assert [event["node"] for event in events] == nodes
    assert events[-1]["status"] == "failed"
    assert events[-1]["error"]
    assert all(event["run_id"] == result.run_id for event in events)
    meta = read_json(result.run_dir / "run_meta.json")
    assert meta["status"] == "failed"
    assert meta["elapsed_ms"] >= 0


@pytest.mark.parametrize("sample", ["math_001", "science_001", "chinese_001"])
def test_b_samples_execute_only_draft_and_plan(tmp_path, sample):
    raw = read_json(ROOT / f"data/inputs/{sample}.json")
    provider = build_mock_direct_write_provider(LessonTask.model_validate(raw))
    result = run_b(tmp_path, raw, provider=provider, comparison_id="sample-pair")

    assert result.status == "completed" and result.validation_valid
    assert "outline" not in result.state
    assert {path.name for path in result.run_dir.iterdir()} == {
        "input.json", "run_meta.json", "01_normalized.json", "03_direct_writer.json",
        "04_formatter.json", "05_schema_validation.json", "state.json", "trace.jsonl", "final.json",
    }
    assert read_json(result.run_dir / "input.json") == raw
    draft = read_json(result.run_dir / "03_direct_writer.json")
    LessonDraft.model_validate(draft)
    final = read_json(result.final_artifact_path)
    LessonPlan.model_validate(final)
    assert validate_formatted_plan(final, expected_task=result.state["task"]).valid
    assert final == result.state["formatted_plan"] == read_json(result.run_dir / "04_formatter.json")
    assert result.state == read_json(result.run_dir / "state.json")
    assert [call["schema"] for call in provider.call_log] == ["LessonDraft", "LessonPlan"]
    payloads = [json.loads(call["user"]) for call in provider.call_log]
    assert payloads[0] == {"task": result.state["task"], "knowledge": []}
    assert payloads[1] == {"task_metadata_to_preserve": result.state["task"], "draft": draft}

    events = trace(result)
    assert tuple(event["node"] for event in events) == DIRECT_WRITE_NODE_ORDER
    assert all(event["status"] == "success" and event["error"] is None for event in events)
    meta = read_json(result.run_dir / "run_meta.json")
    assert meta["pipeline_id"] == "direct_write" and meta["pipeline_version"] == "1"
    assert meta["comparison_id"] == "sample-pair" and meta["metadata_schema_version"] == 1
    assert meta["status"] == "completed" and meta["elapsed_ms"] >= 0
    assert set(meta["prompt_versions"]) == {"direct_writer", "formatter"}
    for node, call in zip(("direct_writer", "formatter"), provider.call_log):
        assert meta["prompt_hashes"][node] == sha256(call["system"].encode("utf-8")).hexdigest()
    for event in events:
        assert event["run_id"] == result.run_id and event["token_usage"] is None
        assert not Path(event["artifact_path"]).is_absolute()
        assert (result.run_dir / event["artifact_path"]).is_file()
        if event["node_type"] == "program_node":
            assert event["model_id"] is None and event["provider"] is None
        else:
            assert event["prompt_version"] == meta["prompt_versions"][event["node"]]
            assert event["temperature"] == meta["generation_parameters"][event["node"]]["temperature"]
    assert meta["knowledge"]["direct_writer"]["documents"] == []
    assert meta["knowledge"]["direct_writer"]["status"] == "retrieved"
    assert meta["configuration"]["config_files_loaded"] == []
    assert meta["configuration"]["dotenv_loaded"] is False
    assert meta["request_configuration"]["network_requests"] is False


def test_default_and_explicit_a_are_equivalent_and_all_runs_are_independent(tmp_path):
    providers = [build_mock_phase1_provider(LessonTask.model_validate(TASK)) for _ in range(2)]
    default = run_lesson_pipeline(TASK, provider=providers[0], runs_dir=tmp_path, comparison_id="pair")
    before = {path.name: path.read_bytes() for path in default.run_dir.iterdir()}
    explicit = run_lesson_pipeline(TASK, provider=providers[1], runs_dir=tmp_path,
                                   pipeline="outline_then_write", comparison_id="pair")
    first_b = run_b(tmp_path, comparison_id="pair")
    b_before = {path.name: path.read_bytes() for path in first_b.run_dir.iterdir()}
    second_b = run_b(tmp_path, comparison_id="pair")
    results = [default, explicit, first_b, second_b]
    assert all(result.status == "completed" for result in results)
    assert len({result.run_id for result in results}) == 4
    assert before == {path.name: path.read_bytes() for path in default.run_dir.iterdir()}
    assert b_before == {path.name: path.read_bytes() for path in first_b.run_dir.iterdir()}
    assert providers[0].call_log == providers[1].call_log
    assert read_json(default.final_artifact_path) == read_json(explicit.final_artifact_path)
    assert tuple(event["node"] for event in trace(explicit)) == PHASE1_NODE_ORDER
    metadata = [read_json(result.run_dir / "run_meta.json") for result in results]
    assert len({item["input_hash"] for item in metadata}) == 1
    assert len({item["normalized_task_hash"] for item in metadata}) == 1
    assert all(item["comparison_id"] == "pair" for item in metadata)
    assert all("comparison_id" not in result.state["task"] for result in results)


def test_unknown_pipeline_is_rejected_before_directory_or_model_call(tmp_path):
    provider = MockModelProvider()
    with pytest.raises(ValueError, match="Unknown pipeline"):
        run_lesson_pipeline(TASK, pipeline="typo", provider=provider, runs_dir=tmp_path / "new")
    assert provider.call_log == []
    assert not (tmp_path / "new").exists()


@pytest.mark.parametrize("raw", [None, [], ["invalid"], "invalid", 42, {},
                                  {**TASK, "requirements": "wrong type"},
                                  {**TASK, "topic": " "}])
def test_b_invalid_input_preserves_raw_value_without_models(tmp_path, raw):
    provider = MockModelProvider()
    result = run_b(tmp_path, raw, provider=provider)
    assert_failed(result, ["normalize_input"])
    assert read_json(result.run_dir / "input.json") == raw
    assert result.state["task"] == raw and provider.call_log == []
    meta = read_json(result.run_dir / "run_meta.json")
    assert meta["normalized_task_hash"] is None
    assert meta["knowledge"]["direct_writer"]["status"] == "not_called"


@pytest.mark.parametrize("schema_name,node", [("LessonDraft", "direct_writer"), ("LessonPlan", "formatter")])
def test_b_model_failure_stops_downstream(tmp_path, monkeypatch, schema_name, node):
    provider = build_mock_direct_write_provider(LessonTask.model_validate(TASK))
    original = provider.generate_structured
    attempted = []

    def generate(**kwargs):
        attempted.append(kwargs["schema"].__name__)
        if attempted[-1] == schema_name:
            raise ModelProviderError(f"injected {node}")
        return original(**kwargs)

    monkeypatch.setattr(provider, "generate_structured", generate)
    result = run_b(tmp_path, provider=provider)
    expected = list(DIRECT_WRITE_NODE_ORDER[:DIRECT_WRITE_NODE_ORDER.index(node) + 1])
    assert_failed(result, expected)
    assert len(attempted) == len(expected) - 1 and attempted[-1] == schema_name
    assert "validation" not in result.state
    assert trace(result)[-1]["token_usage"] is None


@pytest.mark.parametrize("field", ["teacher_activity", "student_activity", "assessment"])
@pytest.mark.parametrize("invalid_kind", ["missing", "blank"])
def test_invalid_direct_draft_never_reaches_formatter(tmp_path, monkeypatch, field, invalid_kind):
    provider = build_mock_direct_write_provider(LessonTask.model_validate(TASK))
    original = provider.generate_structured

    def generate(**kwargs):
        response = original(**kwargs)
        value = deepcopy(response.value.model_dump(mode="json"))
        if invalid_kind == "missing":
            del value["stages"][0][field]
        else:
            value["stages"][0][field] = "   "
        kwargs["schema"].model_validate(value)
        return response

    monkeypatch.setattr(provider, "generate_structured", generate)
    result = run_b(tmp_path, provider=provider)
    assert_failed(result, ["normalize_input", "direct_writer"])
    assert [call["schema"] for call in provider.call_log] == ["LessonDraft"]
    assert not (result.run_dir / "03_direct_writer.json").exists()


@pytest.mark.parametrize("invalid_kind", ["duration", "task"])
def test_b_final_validation_failure_has_no_final(tmp_path, invalid_kind):
    overrides = {"task_id": "changed", "subject": "changed", "grade": "changed", "topic": "changed",
                 "duration": "changed", "requirements": ["changed"], "language": "changed"}
    provider = build_mock_direct_write_provider(
        LessonTask.model_validate(TASK), invalid_final_duration=invalid_kind == "duration",
        final_task_overrides=overrides if invalid_kind == "task" else None,
    )
    result = run_b(tmp_path, provider=provider)
    assert_failed(result, list(DIRECT_WRITE_NODE_ORDER))
    assert not result.validation_valid
    if invalid_kind == "task":
        for field in overrides:
            assert any(f"task.{field} must match" in error for error in result.state["errors"])


@pytest.mark.parametrize("failure_point", ["final_write", "state_write", "save_trace"])
def test_b_save_failure_removes_partial_or_completed_final(tmp_path, monkeypatch, failure_point):
    original_save = ArtifactStore.save_json
    original_append = TraceStore.append
    injected = False

    def save(store, filename, value):
        nonlocal injected
        if not injected and ((failure_point == "final_write" and filename == "final.json")
                             or (failure_point == "state_write" and filename == "state.json")):
            injected = True
            if filename == "final.json":
                (store.run_dir / filename).write_text('{"partial":', encoding="utf-8")
            raise OSError(f"injected {failure_point}")
        return original_save(store, filename, value)

    def append(store, event):
        nonlocal injected
        if not injected and failure_point == "save_trace" and event["node"] == "save":
            injected = True
            raise OSError("injected save_trace")
        return original_append(store, event)

    monkeypatch.setattr(ArtifactStore, "save_json", save)
    monkeypatch.setattr(TraceStore, "append", append)
    result = run_b(tmp_path)
    assert injected
    assert_failed(result, list(DIRECT_WRITE_NODE_ORDER))


@pytest.mark.parametrize("pipeline", ["outline_then_write", "direct_write"])
@pytest.mark.parametrize("phase", ["initial", "normalized", "knowledge", "terminal"])
def test_metadata_write_failure_is_not_success(tmp_path, monkeypatch, pipeline, phase):
    original = ArtifactStore.save_json
    injected = False
    first_agent = "direct_writer" if pipeline == "direct_write" else "outline_planner"

    def save(store, filename, value):
        nonlocal injected
        if filename == "run_meta.json" and not injected:
            reached = (
                phase == "initial"
                or (phase == "normalized" and value["normalized_task_hash"] is not None)
                or (phase == "knowledge" and value["knowledge"][first_agent]["status"] == "retrieved")
                or (phase == "terminal" and value["status"] == "completed")
            )
            if reached:
                injected = True
                if phase == "terminal":
                    assert (store.run_dir / "final.json").is_file()
                (store.run_dir / filename).write_text('{"partial":', encoding="utf-8")
                raise OSError(f"injected metadata {phase}")
        return original(store, filename, value)

    monkeypatch.setattr(ArtifactStore, "save_json", save)
    result = run_lesson_pipeline(TASK, pipeline=pipeline, runs_dir=tmp_path)
    order = list(DIRECT_WRITE_NODE_ORDER if pipeline == "direct_write" else PHASE1_NODE_ORDER)
    expected = {"initial": ["pipeline"], "normalized": ["normalize_input"],
                "knowledge": ["normalize_input", first_agent],
                "terminal": order + ["pipeline_metadata"]}[phase]
    assert injected
    assert_failed(result, expected)


@pytest.mark.parametrize("pipeline", ["outline_then_write", "direct_write"])
def test_fixed_knowledge_is_persisted_before_models_even_if_generation_fails(tmp_path, monkeypatch, pipeline):
    documents = [{"source": "fixture", "version": "v1", "content": "固定资料"}]
    requests = []

    class Retriever:
        def retrieve(self, **kwargs):
            requests.append(kwargs)
            return deepcopy(documents)

    factory = build_mock_direct_write_provider if pipeline == "direct_write" else build_mock_phase1_provider
    provider = factory(LessonTask.model_validate(TASK))
    original = provider.generate_structured
    expected_nodes = ["direct_writer"] if pipeline == "direct_write" else ["outline_planner", "writer"]
    seen = []

    def generate(**kwargs):
        node = expected_nodes[len(seen)]
        meta = read_json(next(tmp_path.iterdir()) / "run_meta.json")
        snapshot = meta["knowledge"][node]
        assert snapshot["documents"] == json.loads(kwargs["user_prompt"])["knowledge"] == documents
        assert snapshot["status"] == "retrieved" and snapshot["snapshot_hash"]
        seen.append(node)
        if node == expected_nodes[-1]:
            raise ModelProviderError("stop after snapshot")
        return original(**kwargs)

    monkeypatch.setattr(provider, "generate_structured", generate)
    result = run_lesson_pipeline(TASK, pipeline=pipeline, provider=provider, retriever=Retriever(), runs_dir=tmp_path)
    assert_failed(result, ["normalize_input", *expected_nodes])
    assert seen == expected_nodes
    assert [item["query"] for item in requests] == (
        [f"为{TASK['topic']}规划教学结构", f"为{TASK['topic']}撰写教学活动"]
        if pipeline == "outline_then_write" else [f"为{TASK['topic']}撰写教学活动"]
    )


def test_retrieval_failure_is_distinct_from_empty_knowledge(tmp_path):
    class Retriever:
        def retrieve(self, **kwargs):
            raise RuntimeError("retrieval unavailable")

    provider = MockModelProvider()
    result = run_b(tmp_path, provider=provider, retriever=Retriever())
    assert_failed(result, ["normalize_input", "direct_writer"])
    record = read_json(result.run_dir / "run_meta.json")["knowledge"]["direct_writer"]
    assert record["status"] == "failed" and record["error"] == "retrieval unavailable"
    assert record["documents"] is None and record["snapshot_hash"] is None
    assert provider.call_log == []


def test_hashes_distinguish_raw_input_and_normalized_task(tmp_path):
    raw = {"task_id": " alias ", "subject_name": " 数学 ", "grade_level": " 七年级 ",
           "lesson_topic": " 方程 ", "requirements": [" 说明步骤 "], "duration": " "}
    first = run_b(tmp_path, raw)
    normalized = first.state["task"]
    second = run_b(tmp_path, dict(reversed(list(raw.items()))))
    third = run_b(tmp_path, normalized)
    changed = run_b(tmp_path, {**normalized, "requirements": ["different"]})
    a, b, c, d = [read_json(item.run_dir / "run_meta.json") for item in (first, second, third, changed)]
    assert a["input_hash"] == b["input_hash"] != c["input_hash"]
    assert a["normalized_task_hash"] == b["normalized_task_hash"] == c["normalized_task_hash"]
    assert d["input_hash"] != c["input_hash"] and d["normalized_task_hash"] != c["normalized_task_hash"]
    assert read_json(third.final_artifact_path)["task"] == normalized


def test_git_unavailable_is_unknown_and_does_not_block_generation(tmp_path, monkeypatch):
    def unavailable(*args, **kwargs):
        raise FileNotFoundError("git unavailable")

    monkeypatch.setattr(run_metadata.subprocess, "run", unavailable)
    result = run_b(tmp_path)
    assert result.status == "completed"
    meta = read_json(result.run_dir / "run_meta.json")
    assert meta["git_commit"] is None and meta["git_dirty"] is None
    assert meta["git_notes"] == ["git_information_unavailable"]
    assert meta["environment"]["packages"]["pydantic"]


@pytest.mark.parametrize("status,warning,dirty", [("", "", False), ("?? new.py", "", True), ("", "warning", None)])
def test_git_provenance_reports_actual_checkout_or_uncertainty(monkeypatch, status, warning, dirty):
    def git(command, **kwargs):
        if "--show-toplevel" in command:
            return subprocess.CompletedProcess(command, 0, str(ROOT), "")
        if "HEAD" in command:
            return subprocess.CompletedProcess(command, 0, "a" * 40, "")
        return subprocess.CompletedProcess(command, 0, status, warning)

    monkeypatch.setattr(run_metadata.subprocess, "run", git)
    metadata = run_metadata.code_provenance()
    assert metadata["git_commit"] == "a" * 40 and metadata["git_dirty"] is dirty


def test_cli_rejects_unknown_pipeline_before_loading_input_or_provider(tmp_path):
    completed = subprocess.run(
        [sys.executable, str(ROOT / "examples/04_lesson_pipeline.py"),
         "--input", str(tmp_path / "missing.json"), "--real", "--pipeline", "invalid",
         "--runs-dir", str(tmp_path / "runs")],
        capture_output=True, text=True, encoding="utf-8", timeout=20,
    )
    assert completed.returncode == 2
    assert "invalid choice" in completed.stderr
    assert "OPENAI_API_KEY" not in completed.stderr and "FileNotFoundError" not in completed.stderr
    assert not (tmp_path / "runs").exists()
