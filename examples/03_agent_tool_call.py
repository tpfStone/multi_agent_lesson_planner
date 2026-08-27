from __future__ import annotations

import argparse

from lesson_agents.agents.calculator_agent import CalculatorAgent
from lesson_agents.models.base import ToolCall
from lesson_agents.models.mock import MockModelProvider
from lesson_agents.models.provider import OpenAIModelProvider


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent -> model tool call -> CalculatorTool demo")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--mock", action="store_true")
    mode.add_argument("--real", action="store_true")
    args = parser.parse_args()

    provider = (
        OpenAIModelProvider.from_env()
        if args.real
        else MockModelProvider(
            tool_calls=[
                ToolCall(
                    name="calculator",
                    arguments={"operation": "multiply", "left": 12, "right": 8},
                )
            ]
        )
    )
    result = CalculatorAgent(provider).run("请计算 12 乘以 8。")
    print(f"agent tool call: {result.tool_call.name}({result.tool_call.arguments})")
    print(f"tool result: {result.result}")


if __name__ == "__main__":
    main()

