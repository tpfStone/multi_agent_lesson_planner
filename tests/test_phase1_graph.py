import json
from pathlib import Path

from lesson_agents.app import run_lesson_pipeline
from lesson_agents.core.constants import PHASE1_NODE_ORDER


TASK = {
    "task_id": "math_001",
    "subject": "数学",
    "grade": "七年级",
    "topic": "一元一次方程",
    "duration": "45分钟",
}


def _read_trace(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_graph_executes_exact_phase1_path(tmp_path) -> None:
    result = run_lesson_pipeline(TASK, runs_dir=tmp_path)
    events = _read_trace(result.run_dir / "trace.jsonl")

    assert tuple(event["node"] for event in events) == PHASE1_NODE_ORDER
    assert [event["node_type"] for event in events] == [
        "program_node",
        "llm_agent",
        "llm_agent",
        "llm_agent",
        "program_node",
        "program_node",
    ]
    assert all(
        event["artifact_path"] is None or not Path(event["artifact_path"]).is_absolute()
        for event in events
    )
    assert [event["artifact_path"] for event in events] == [
        "01_normalized.json",
        "02_outline_planner.json",
        "03_writer.json",
        "04_formatter.json",
        "05_schema_validation.json",
        "final.json",
    ]


def test_deterministic_nodes_do_not_create_model_calls(tmp_path) -> None:
    result = run_lesson_pipeline(TASK, runs_dir=tmp_path)
    events = _read_trace(result.run_dir / "trace.jsonl")

    program_events = [event for event in events if event["node_type"] == "program_node"]
    assert all(event["provider"] is None for event in program_events)
    assert all(event["model_id"] is None for event in program_events)


def test_run_meta_is_derived_from_actual_agent_and_provider_metadata(tmp_path) -> None:
    result = run_lesson_pipeline(TASK, runs_dir=tmp_path)
    events = _read_trace(result.run_dir / "trace.jsonl")
    agent_events = {event["node"]: event for event in events if event["node_type"] == "llm_agent"}
    run_meta = json.loads((result.run_dir / "run_meta.json").read_text(encoding="utf-8"))

    assert {event["provider"] for event in agent_events.values()} == {run_meta["provider"]}
    assert {event["model_id"] for event in agent_events.values()} == {run_meta["model_id"]}
    assert run_meta["prompt_versions"] == {
        node: event["prompt_version"] for node, event in agent_events.items()
    }
    assert run_meta["generation_parameters"] == {
        node: {"temperature": event["temperature"]} for node, event in agent_events.items()
    }
    assert run_meta["config_version"] is None
    assert run_meta["configuration"]["config_files_loaded"] == []
    assert run_meta["configuration"]["dotenv_loaded"] is False
    assert run_meta["configuration"]["provider_configuration_source"] == "scripted_arguments"
