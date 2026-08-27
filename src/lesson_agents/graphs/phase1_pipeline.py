from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from lesson_agents.agents.formatter import FormatterAgent
from lesson_agents.agents.outline_planner import OutlinePlannerAgent
from lesson_agents.agents.writer import WriterAgent
from lesson_agents.core.constants import PHASE1_NODE_ORDER
from lesson_agents.core.schemas import LessonDraft, LessonOutline, LessonTask
from lesson_agents.core.state import LessonPlanState
from lesson_agents.knowledge.base import KnowledgeRetriever
from lesson_agents.models.base import ModelProvider
from lesson_agents.nodes.normalize import make_normalize_node
from lesson_agents.nodes.save import make_save_node
from lesson_agents.nodes.schema_validate import make_schema_validate_node
from lesson_agents.storage.run_context import RunContext


def _retrieve(retriever: KnowledgeRetriever, task: LessonTask, query: str) -> list[dict]:
    return retriever.retrieve(
        subject=task.subject,
        grade=task.grade,
        topic=task.topic,
        query=query,
    )


def build_phase1_graph(
    *,
    provider: ModelProvider,
    retriever: KnowledgeRetriever,
    context: RunContext,
    aliases: dict[str, str] | None = None,
):
    planner = OutlinePlannerAgent(provider)
    writer_agent = WriterAgent(provider)
    formatter_agent = FormatterAgent(provider)
    context.runtime_metadata = {
        "provider": provider.provider_name,
        "model_id": provider.model_id,
        "base_url": getattr(provider, "base_url", None),
        "provider_configuration_source": getattr(provider, "configuration_source", "unknown"),
        "agents": {
            "outline_planner": {
                "prompt_version": planner.prompt_version,
                "temperature": planner.temperature,
            },
            "writer": {
                "prompt_version": writer_agent.prompt_version,
                "temperature": writer_agent.temperature,
            },
            "formatter": {
                "prompt_version": formatter_agent.prompt_version,
                "temperature": formatter_agent.temperature,
            },
        },
    }

    def outline_planner(state: LessonPlanState) -> dict:
        span = context.traces.start_span(
            node="outline_planner",
            node_type="llm_agent",
            provider=provider.provider_name,
            model_id=provider.model_id,
            prompt_version=planner.prompt_version,
            temperature=planner.temperature,
        )
        try:
            task = LessonTask.model_validate(state["task"])
            knowledge = _retrieve(retriever, task, f"为{task.topic}规划教学结构")
            response = planner.run(task=task, knowledge=knowledge)
            update = {
                "outline": response.value.model_dump(mode="json"),
                "current_stage": "outline_planned",
                "status": "running",
            }
            artifact = context.artifacts.save_json("02_outline_planner.json", update["outline"])
            context.capture(state, update)
            span.finish(status="success", artifact_path=artifact, metadata=response.metadata)
            return update
        except Exception as exc:
            span.finish(status="failed", artifact_path=None, error=str(exc))
            context.persist_failure(state, node="outline_planner", error=exc)
            raise

    def writer(state: LessonPlanState) -> dict:
        span = context.traces.start_span(
            node="writer",
            node_type="llm_agent",
            provider=provider.provider_name,
            model_id=provider.model_id,
            prompt_version=writer_agent.prompt_version,
            temperature=writer_agent.temperature,
        )
        try:
            task = LessonTask.model_validate(state["task"])
            outline = LessonOutline.model_validate(state["outline"])
            knowledge = _retrieve(retriever, task, f"为{task.topic}撰写教学活动")
            response = writer_agent.run(task=task, outline=outline, knowledge=knowledge)
            update = {
                "draft": response.value.model_dump(mode="json"),
                "current_stage": "draft_written",
                "status": "running",
            }
            artifact = context.artifacts.save_json("03_writer.json", update["draft"])
            context.capture(state, update)
            span.finish(status="success", artifact_path=artifact, metadata=response.metadata)
            return update
        except Exception as exc:
            span.finish(status="failed", artifact_path=None, error=str(exc))
            context.persist_failure(state, node="writer", error=exc)
            raise

    def formatter(state: LessonPlanState) -> dict:
        span = context.traces.start_span(
            node="formatter",
            node_type="llm_agent",
            provider=provider.provider_name,
            model_id=provider.model_id,
            prompt_version=formatter_agent.prompt_version,
            temperature=formatter_agent.temperature,
        )
        try:
            task = LessonTask.model_validate(state["task"])
            draft = LessonDraft.model_validate(state["draft"])
            response = formatter_agent.run(task=task, draft=draft)
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

    graph = StateGraph(LessonPlanState)
    graph.add_node("normalize_input", make_normalize_node(context, aliases=aliases))
    graph.add_node("outline_planner", outline_planner)
    graph.add_node("writer", writer)
    graph.add_node("formatter", formatter)
    graph.add_node("schema_validate", make_schema_validate_node(context))
    graph.add_node("save", make_save_node(context))

    graph.add_edge(START, PHASE1_NODE_ORDER[0])
    for current, following in zip(PHASE1_NODE_ORDER, PHASE1_NODE_ORDER[1:]):
        graph.add_edge(current, following)
    graph.add_edge(PHASE1_NODE_ORDER[-1], END)
    return graph
