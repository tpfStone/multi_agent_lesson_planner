from __future__ import annotations

from lesson_agents.core.state import LessonPlanState
from lesson_agents.storage.run_context import RunContext


def make_save_node(context: RunContext):
    def save(state: LessonPlanState) -> dict:
        span = context.traces.start_span(node="save", node_type="program_node")
        try:
            validation = state.get("validation") or {}
            if validation.get("valid") is True:
                final_artifact = context.artifacts.save_json("final.json", state["formatted_plan"])
                update = {"current_stage": "completed", "status": "completed"}
                completed_state = context.capture(state, update)
                context.artifacts.save_json("state.json", completed_state)
                span.finish(status="success", artifact_path=final_artifact)
                return update

            update = {"current_stage": "failed", "status": "failed"}
            failed_state = context.capture(state, update)
            state_artifact = context.artifacts.save_json("state.json", failed_state)
            error = "; ".join(validation.get("errors", [])) or "Schema validation failed"
            span.finish(status="failed", artifact_path=state_artifact, error=error)
            return update
        except Exception as exc:
            span.finish(status="failed", artifact_path=None, error=str(exc))
            context.persist_failure(state, node="save", error=exc)
            raise

    return save

