from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from lesson_agents.core.exceptions import ToolExecutionError
from lesson_agents.models.base import ModelProvider, ToolCall
from lesson_agents.prompts import load_prompt
from lesson_agents.tools.calculator import CalculatorTool


@dataclass(frozen=True, slots=True)
class CalculatorAgentResult:
    tool_call: ToolCall
    result: Decimal


class CalculatorAgent:
    """Demo-only role agent that asks a model to select and call a tool."""

    def __init__(self, provider: ModelProvider, tool: CalculatorTool | None = None) -> None:
        self._provider = provider
        self._tool = tool or CalculatorTool()
        self._system_prompt = load_prompt("calculator_agent_v1.txt")

    def run(self, question: str) -> CalculatorAgentResult:
        response = self._provider.generate_tool_call(
            system_prompt=self._system_prompt,
            user_prompt=question,
            tools=[self._tool.definition()],
            temperature=0.0,
        )
        call = response.value
        if call.name != self._tool.name:
            raise ToolExecutionError(f"Agent selected unsupported tool: {call.name}")
        return CalculatorAgentResult(tool_call=call, result=self._tool.invoke(call.arguments))
