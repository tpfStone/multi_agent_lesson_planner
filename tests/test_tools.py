from decimal import Decimal

import pytest

from lesson_agents.agents.calculator_agent import CalculatorAgent
from lesson_agents.core.exceptions import ToolExecutionError
from lesson_agents.models.base import ToolCall
from lesson_agents.models.mock import MockModelProvider
from lesson_agents.tools.calculator import CalculatorTool
from lesson_agents.tools.file_reader import FileReaderTool


def test_calculator_normal_operations() -> None:
    tool = CalculatorTool()

    assert tool.invoke({"operation": "add", "left": 12, "right": 3}) == Decimal("15")
    assert tool.invoke({"operation": "divide", "left": 7, "right": 2}) == Decimal("3.5")


def test_calculator_rejects_invalid_operations_and_division_by_zero() -> None:
    tool = CalculatorTool()

    with pytest.raises(ToolExecutionError):
        tool.invoke({"operation": "power", "left": 2, "right": 8})
    with pytest.raises(ToolExecutionError):
        tool.invoke({"operation": "divide", "left": 1, "right": 0})


def test_agent_requests_and_dispatches_a_real_tool_call() -> None:
    provider = MockModelProvider(
        tool_calls=[
            ToolCall(
                name="calculator",
                arguments={"operation": "multiply", "left": 12, "right": 8},
            )
        ]
    )

    result = CalculatorAgent(provider).run("请计算 12 乘以 8。")

    assert result.result == Decimal("96")
    assert result.tool_call.name == "calculator"
    assert provider.call_log == [
        {
            "kind": "tool_call",
            "system": (
                "You are a careful arithmetic assistant. Use the provided calculator "
                "tool for arithmetic and do not calculate the answer yourself."
            ),
            "user": "请计算 12 乘以 8。",
            "tools": ["calculator"],
        }
    ]


def test_file_reader_is_restricted_to_material_directory(tmp_path) -> None:
    materials = tmp_path / "materials"
    materials.mkdir()
    lesson = materials / "lesson.txt"
    lesson.write_text("课程材料", encoding="utf-8")
    outside = tmp_path / "secret.txt"
    outside.write_text("不可读取", encoding="utf-8")
    tool = FileReaderTool(materials)

    assert tool.invoke("lesson.txt") == "课程材料"
    with pytest.raises(ToolExecutionError):
        tool.invoke("../secret.txt")

