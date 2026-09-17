"""Phase 1 acceptance checks: persisted results and failure boundaries only."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from lesson_agents.app import DEFAULT_ALIASES, run_lesson_pipeline
from lesson_agents.core.constants import PHASE1_NODE_ORDER
from lesson_agents.core.exceptions import ModelProviderError
from lesson_agents.core.schemas import LessonDraft, LessonOutline, LessonPlan, LessonTask
from lesson_agents.mock_scenario import build_mock_phase1_provider
from lesson_agents.models.mock import MockModelProvider
from lesson_agents.nodes.normalize import normalize_task_data
from lesson_agents.nodes.schema_validate import validate_formatted_plan
from lesson_agents.storage.artifact_store import ArtifactStore
from lesson_agents.storage.trace_store import TraceStore


INPUTS = Path(__file__).resolve().parents[1] / "data" / "inputs"
TASK = json.loads((INPUTS / "math_001.json").read_text(encoding="utf-8"))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_trace(run_dir):
    return [json.loads(line) for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()]


def assert_failed(result, expected_nodes):
    assert result.status == "failed"
    assert result.final_artifact_path is None
    assert not (result.run_dir / "final.json").exists()
    state = read_json(result.run_dir / "state.json")
    assert state == result.state
    assert state["status"] == "failed"
    assert state["errors"]
    events = read_trace(result.run_dir)
    assert [event["node"] for event in events] == expected_nodes
    assert all(event["status"] == "success" for event in events[:-1])
    assert events[-1]["status"] == "failed"
    assert events[-1]["error"]
    assert all(event["run_id"] == result.run_id for event in events)


@pytest.mark.parametrize("sample", ["math_001", "science_001", "chinese_001"])
def test_repository_samples_have_consistent_artifacts_and_actual_calls(tmp_path, monkeypatch, sample):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    raw = read_json(INPUTS / f"{sample}.json")
    task = LessonTask.model_validate(normalize_task_data(raw, DEFAULT_ALIASES))
    provider = build_mock_phase1_provider(task)
    assert isinstance(provider, MockModelProvider)

    result = run_lesson_pipeline(raw, provider=provider, runs_dir=tmp_path)

    assert result.status == "completed"
    assert result.validation_valid is True
    assert read_json(result.run_dir / "input.json") == raw
    normalized = read_json(result.run_dir / "01_normalized.json")
    assert normalized == task.model_dump(mode="json")
    LessonOutline.model_validate(read_json(result.run_dir / "02_outline_planner.json"))
    draft = LessonDraft.model_validate(read_json(result.run_dir / "03_writer.json"))
    final = read_json(result.run_dir / "final.json")
    plan = LessonPlan.model_validate(final)
    assert final["task"] == normalized
    assert validate_formatted_plan(final, expected_task=normalized).valid
    assert final == read_json(result.run_dir / "04_formatter.json")
    assert result.state == read_json(result.run_dir / "state.json")
    assert result.state["formatted_plan"] == final
    assert result.state["run_id"] == result.run_id
    assert result.state["current_stage"] == "completed"
    assert result.state["errors"] == []
    assert result.state["validation"] == read_json(result.run_dir / "05_schema_validation.json")
    for stage in [*draft.stages, *plan.stages]:
        assert stage.teacher_activity.strip()
        assert stage.student_activity.strip()
        assert stage.assessment.strip()

    events = read_trace(result.run_dir)
    assert tuple(event["node"] for event in events) == PHASE1_NODE_ORDER
    assert all(event["status"] == "success" and event["error"] is None for event in events)
    assert all(event["run_id"] == result.run_id for event in events)
    for event in events:
        assert event["latency_ms"] >= 0
        assert event["started_at"] <= event["ended_at"]
        assert not Path(event["artifact_path"]).is_absolute()
        assert (result.run_dir / event["artifact_path"]).is_file()
    assert [call["schema"] for call in provider.call_log] == ["LessonOutline", "LessonDraft", "LessonPlan"]
    payloads = [json.loads(call["user"]) for call in provider.call_log]
    assert payloads[0]["task"] == normalized
    assert payloads[1]["outline"] == result.state["outline"]
    assert payloads[2]["draft"] == result.state["draft"]
    assert payloads[2]["task_metadata_to_preserve"] == normalized

    meta = read_json(result.run_dir / "run_meta.json")
    assert meta["run_id"] == result.run_id
    assert meta["provider"] == provider.provider_name == "mock"
    assert meta["model_id"] == provider.model_id
    assert meta["configuration"]["dotenv_loaded"] is False
    assert meta["configuration"]["config_files_loaded"] == []
    for event in events[1:4]:
        assert event["provider"] == meta["provider"]
        assert event["model_id"] == meta["model_id"]
        assert event["prompt_version"] == meta["prompt_versions"][event["node"]]
        assert event["temperature"] == meta["generation_parameters"][event["node"]]["temperature"]
    assert {path.name for path in result.run_dir.iterdir()} == {
        "input.json", "run_meta.json", "01_normalized.json", "02_outline_planner.json",
        "03_writer.json", "04_formatter.json", "05_schema_validation.json",
        "state.json", "trace.jsonl", "final.json",
    }


def test_normalization_aliases_whitespace_and_defaults_reach_final(tmp_path):
    raw = {"task_id": " alias_001 ", "subject_name": " 数学 ", "grade_level": " 七年级 ",
           "lesson_topic": " 方程 ", "duration": " ", "requirements": [" 结构化教案 "]}
    expected = {"task_id": "alias_001", "subject": "数学", "grade": "七年级",
                "topic": "方程", "duration": None, "requirements": ["结构化教案"], "language": "zh-CN"}
    result = run_lesson_pipeline(raw, runs_dir=tmp_path)
    assert result.status == "completed"
    assert result.state["task"] == expected
    assert read_json(result.run_dir / "final.json")["task"] == expected
    assert read_json(result.run_dir / "input.json") == raw


def test_repeated_runs_do_not_overwrite_previous_artifacts(tmp_path):
    first = run_lesson_pipeline(TASK, runs_dir=tmp_path)
    before = {path.name: path.read_bytes() for path in first.run_dir.iterdir()}
    second = run_lesson_pipeline(TASK, runs_dir=tmp_path)
    assert first.status == second.status == "completed"
    assert first.run_id != second.run_id
    assert first.run_dir != second.run_dir
    assert before == {path.name: path.read_bytes() for path in first.run_dir.iterdir()}
    assert all(event["run_id"] == second.run_id for event in read_trace(second.run_dir))


@pytest.mark.parametrize("raw", [
    {}, {**TASK, "topic": "   "}, {**TASK, "requirements": "wrong type"},
    {**TASK, "unknown_field": True}, {key: value for key, value in TASK.items() if key != "topic"},
], ids=["empty", "blank-topic", "wrong-type", "unknown-field", "missing-topic"])
def test_invalid_input_is_persisted_before_any_model_call(tmp_path, raw):
    provider = MockModelProvider()
    result = run_lesson_pipeline(raw, provider=provider, runs_dir=tmp_path)
    assert_failed(result, ["normalize_input"])
    assert provider.call_log == []
    assert read_json(result.run_dir / "input.json") == raw
    assert {path.name for path in result.run_dir.iterdir()} == {
        "input.json", "run_meta.json", "state.json", "trace.jsonl",
    }


@pytest.mark.parametrize("raw", [None, [], ["invalid"], "invalid", 42],
                         ids=["null", "empty-array", "array", "string", "number"])
def test_non_object_json_input_is_rejected_with_original_input_and_failure_records(tmp_path, raw):
    result = run_lesson_pipeline(raw, runs_dir=tmp_path)
    assert_failed(result, ["normalize_input"])
    assert read_json(result.run_dir / "input.json") == raw
    assert result.state["task"] == raw
    assert any("JSON object" in error for error in result.state["errors"])


@pytest.mark.parametrize("schema_name,node", [
    ("LessonOutline", "outline_planner"), ("LessonDraft", "writer"), ("LessonPlan", "formatter"),
])
def test_model_exception_at_each_agent_stops_downstream_work(tmp_path, monkeypatch, schema_name, node):
    provider = build_mock_phase1_provider(LessonTask.model_validate(TASK))
    original = provider.generate_structured
    attempted = []

    def fail_at_node(**kwargs):
        attempted.append(kwargs["schema"].__name__)
        if attempted[-1] == schema_name:
            raise ModelProviderError(f"injected failure at {node}")
        return original(**kwargs)

    monkeypatch.setattr(provider, "generate_structured", fail_at_node)
    result = run_lesson_pipeline(TASK, provider=provider, runs_dir=tmp_path)
    expected_nodes = list(PHASE1_NODE_ORDER[:PHASE1_NODE_ORDER.index(node) + 1])
    assert_failed(result, expected_nodes)
    assert attempted[-1] == schema_name
    assert len(attempted) == len(expected_nodes) - 1
    assert any(f"injected failure at {node}" in error for error in result.state["errors"])
    assert "validation" not in result.state


@pytest.mark.parametrize("field", ["teacher_activity", "student_activity", "assessment"])
def test_blank_final_stage_details_fail_without_final_artifact(tmp_path, monkeypatch, field):
    provider = build_mock_phase1_provider(LessonTask.model_validate(TASK))
    original = provider.generate_structured

    def invalid_response(**kwargs):
        response = original(**kwargs)
        if kwargs["schema"] is LessonPlan:
            value = deepcopy(response.value.model_dump(mode="json"))
            value["stages"][0][field] = "   "
            # Exercise the provider's normal Pydantic boundary for malformed output.
            kwargs["schema"].model_validate(value)
        return response

    monkeypatch.setattr(provider, "generate_structured", invalid_response)
    result = run_lesson_pipeline(TASK, provider=provider, runs_dir=tmp_path)
    assert_failed(result, list(PHASE1_NODE_ORDER[:4]))
    assert any(field in error for error in result.state["errors"])


@pytest.mark.parametrize("failure_point", ["final_write", "state_write", "save_trace"])
def test_save_failure_never_leaves_a_success_final(tmp_path, monkeypatch, failure_point):
    original_save = ArtifactStore.save_json
    original_append = TraceStore.append
    injected = False

    def fail_save(store, filename, value):
        nonlocal injected
        if not injected and (
            (failure_point == "final_write" and filename == "final.json")
            or (failure_point == "state_write" and filename == "state.json")
        ):
            injected = True
            if filename == "final.json":
                (store.run_dir / filename).write_text('{"partial":', encoding="utf-8")
            raise OSError(f"injected {failure_point}")
        return original_save(store, filename, value)

    def fail_trace(store, event):
        nonlocal injected
        if not injected and failure_point == "save_trace" and event["node"] == "save":
            injected = True
            raise OSError("injected save_trace")
        return original_append(store, event)

    monkeypatch.setattr(ArtifactStore, "save_json", fail_save)
    monkeypatch.setattr(TraceStore, "append", fail_trace)
    result = run_lesson_pipeline(TASK, runs_dir=tmp_path)
    assert injected
    assert_failed(result, list(PHASE1_NODE_ORDER))
    assert any(f"injected {failure_point}" in error for error in result.state["errors"])
