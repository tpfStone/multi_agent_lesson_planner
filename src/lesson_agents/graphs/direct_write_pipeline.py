from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from lesson_agents.agents.direct_writer import DirectWriterAgent
from lesson_agents.agents.formatter import FormatterAgent
from lesson_agents.core.constants import DIRECT_WRITE_NODE_ORDER
from lesson_agents.core.schemas import LessonTask
from lesson_agents.core.state import LessonPlanState
from lesson_agents.knowledge.base import KnowledgeRetriever
from lesson_agents.models.base import ModelProvider
from lesson_agents.nodes.formatter import make_formatter_node
from lesson_agents.nodes.normalize import make_normalize_node
from lesson_agents.nodes.save import make_save_node
from lesson_agents.nodes.schema_validate import make_schema_validate_node
from lesson_agents.storage.run_context import RunContext


def build_direct_write_graph(
    *,
    provider: ModelProvider,
    retriever: KnowledgeRetriever,
    context: RunContext,
    aliases: dict[str, str] | None = None,
):
    writer_agent = DirectWriterAgent(provider)
    formatter_agent = FormatterAgent(provider)
    context.runtime_metadata = {
        "provider": provider.provider_name,
        "model_id": provider.model_id,
        "base_url": getattr(provider, "base_url", None),
        "provider_configuration_source": getattr(provider, "configuration_source", "unknown"),
        "knowledge_nodes": ["direct_writer"],
        "agents": {
            "direct_writer": {
                "prompt_version": writer_agent.prompt_version,
                "prompt_hash": writer_agent.prompt_hash,
                "temperature": writer_agent.temperature,
            },
            "formatter": {
                "prompt_version": formatter_agent.prompt_version,
                "prompt_hash": formatter_agent.prompt_hash,
                "temperature": formatter_agent.temperature,
            },
        },
    }

    def direct_writer(state: LessonPlanState) -> dict:
        span = context.traces.start_span(
            node="direct_writer",
            node_type="llm_agent",
            provider=provider.provider_name,
            model_id=provider.model_id,
            prompt_version=writer_agent.prompt_version,
            temperature=writer_agent.temperature,
        )
        try:
            task = LessonTask.model_validate(state["task"])
            knowledge = context.retrieve_knowledge(
                node="direct_writer", retriever=retriever,
                task=task, query=f"为{task.topic}撰写教学活动",
            )
            response = writer_agent.run(task=task, knowledge=knowledge)
            update = {
                "draft": response.value.model_dump(mode="json"),
                "current_stage": "draft_written",
                "status": "running",
            }
            artifact = context.artifacts.save_json("03_direct_writer.json", update["draft"])
            context.capture(state, update)
            span.finish(status="success", artifact_path=artifact, metadata=response.metadata)
            return update
        except Exception as exc:
            span.finish(status="failed", artifact_path=None, error=str(exc))
            context.persist_failure(state, node="direct_writer", error=exc)
            raise

    graph = StateGraph(LessonPlanState)
    graph.add_node("normalize_input", make_normalize_node(context, aliases=aliases))
    graph.add_node("direct_writer", direct_writer)
    graph.add_node(
        "formatter", make_formatter_node(context, provider=provider, agent=formatter_agent)
    )
    graph.add_node("schema_validate", make_schema_validate_node(context))
    graph.add_node("save", make_save_node(context))
    graph.add_edge(START, DIRECT_WRITE_NODE_ORDER[0])
    for current, following in zip(DIRECT_WRITE_NODE_ORDER, DIRECT_WRITE_NODE_ORDER[1:]):
        graph.add_edge(current, following)
    graph.add_edge(DIRECT_WRITE_NODE_ORDER[-1], END)
    return graph
