import json

from lesson_agents.app import run_lesson_pipeline
from lesson_agents.core.schemas import LessonPlan, LessonTask
from lesson_agents.mock_scenario import build_mock_phase1_provider
from lesson_agents.models.mock import MockModelProvider


TASK = {
    "task_id": "math_001",
    "subject": "数学",
    "grade": "七年级",
    "topic": "一元一次方程",
    "duration": "45分钟",
    "requirements": ["包含教学目标、重点难点、教学活动和评价方式", "输出结构化教案"],
}


def test_mock_e2e_creates_all_success_artifacts_without_api_key(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = run_lesson_pipeline(TASK, runs_dir=tmp_path)

    assert result.status == "completed"
    assert result.validation_valid is True
    assert result.final_artifact_path is not None
    expected = {
        "input.json",
        "run_meta.json",
        "01_normalized.json",
        "02_outline_planner.json",
        "03_writer.json",
        "04_formatter.json",
        "05_schema_validation.json",
        "final.json",
        "state.json",
        "trace.jsonl",
    }
    assert {path.name for path in result.run_dir.iterdir()} == expected
    LessonPlan.model_validate_json(result.final_artifact_path.read_text(encoding="utf-8"))


def test_validation_failure_saves_state_and_trace_but_not_final(tmp_path) -> None:
    task = LessonTask.model_validate(TASK)
    provider = build_mock_phase1_provider(task, invalid_final_duration=True)

    result = run_lesson_pipeline(TASK, provider=provider, runs_dir=tmp_path)

    assert result.status == "failed"
    assert result.validation_valid is False
    assert result.final_artifact_path is None
    assert not (result.run_dir / "final.json").exists()
    state = json.loads((result.run_dir / "state.json").read_text(encoding="utf-8"))
    events = [
        json.loads(line)
        for line in (result.run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert state["status"] == "failed"
    assert any("non-negative" in error for error in state["errors"])
    assert events[-2]["node"] == "schema_validate"
    assert events[-2]["status"] == "failed"
    assert events[-2]["artifact_path"] == "05_schema_validation.json"
    assert events[-1]["node"] == "save"
    assert events[-1]["status"] == "failed"
    assert events[-1]["artifact_path"] == "state.json"


def test_formatter_cannot_change_any_normalized_task_metadata(tmp_path) -> None:
    task = LessonTask.model_validate(TASK)
    provider = build_mock_phase1_provider(
        task,
        final_task_overrides={
            "task_id": "changed_id",
            "subject": "物理",
            "grade": "九年级",
            "topic": "改变后的主题",
            "duration": "40分钟",
            "requirements": ["改变后的要求"],
            "language": "en-US",
        },
    )

    result = run_lesson_pipeline(TASK, provider=provider, runs_dir=tmp_path)

    assert result.status == "failed"
    assert result.final_artifact_path is None
    validation = result.state["validation"]
    assert validation["valid"] is False
    for field_name in (
        "task_id",
        "subject",
        "grade",
        "topic",
        "duration",
        "requirements",
        "language",
    ):
        assert any(f"task.{field_name} must match" in error for error in validation["errors"])
    assert not (result.run_dir / "final.json").exists()


def test_agent_exception_is_persisted_and_stops_the_graph(tmp_path) -> None:
    result = run_lesson_pipeline(TASK, provider=MockModelProvider(), runs_dir=tmp_path)

    assert result.status == "failed"
    assert result.final_artifact_path is None
    assert (result.run_dir / "state.json").exists()
    events = [
        json.loads(line)
        for line in (result.run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["node"] for event in events] == ["normalize_input", "outline_planner"]
    assert events[-1]["status"] == "failed"
