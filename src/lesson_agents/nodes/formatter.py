from __future__ import annotations

from lesson_agents.agents.formatter import FormatterAgent
from lesson_agents.core.schemas import LessonDraft, LessonTask
from lesson_agents.core.state import LessonPlanState
from lesson_agents.models.base import ModelProvider
from lesson_agents.storage.run_context import RunContext


def make_formatter_node(
    context: RunContext, *, provider: ModelProvider, agent: FormatterAgent
):
    def formatter(state: LessonPlanState) -> dict:
        span = context.traces.start_span(
            node="formatter",
            node_type="llm_agent",
            provider=provider.provider_name,
            model_id=provider.model_id,
            prompt_version=agent.prompt_version,
            temperature=agent.temperature,
        )
        try:
            task = LessonTask.model_validate(state["task"])
            draft = LessonDraft.model_validate(state["draft"])
            response = agent.run(task=task, draft=draft)
            update = {
                "formatted_plan": response.value.model_dump(mode="json"),
                "current_stage": "formatted",
                "status": "running",
            }
            artifact = context.artifacts.save_json("04_formatter.json", update["formatted_plan"])
            context.capture(state, update)
            span.finish(status="success", artifact_path=artifact, metadata=response.metadata)
            return update
        except Exception as exc:
            span.finish(status="failed", artifact_path=None, error=str(exc))
            context.persist_failure(state, node="formatter", error=exc)
            raise

    return formatter
