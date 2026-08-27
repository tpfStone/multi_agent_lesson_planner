from __future__ import annotations

from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Any

from lesson_agents.core.exceptions import ToolExecutionError
from lesson_agents.models.base import ToolDefinition


class CalculatorTool:
    name = "calculator"
    description = "Safely perform one arithmetic operation on two decimal numbers."
    allowed_operations = frozenset({"add", "subtract", "multiply", "divide"})

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": sorted(self.allowed_operations)},
                    "left": {"type": "number"},
                    "right": {"type": "number"},
                },
                "required": ["operation", "left", "right"],
                "additionalProperties": False,
            },
        )

    def invoke(self, arguments: dict[str, Any]) -> Decimal:
        if set(arguments) != {"operation", "left", "right"}:
            raise ToolExecutionError("Calculator arguments must be operation, left, and right")

        operation = arguments["operation"]
        if operation not in self.allowed_operations:
            raise ToolExecutionError(f"Unsupported calculator operation: {operation!r}")

        try:
            left = Decimal(str(arguments["left"]))
            right = Decimal(str(arguments["right"]))
        except (InvalidOperation, ValueError) as exc:
            raise ToolExecutionError("Calculator operands must be finite numbers") from exc

        if not left.is_finite() or not right.is_finite():
            raise ToolExecutionError("Calculator operands must be finite numbers")

        try:
            if operation == "add":
                return left + right
            if operation == "subtract":
                return left - right
            if operation == "multiply":
                return left * right
            return left / right
        except DivisionByZero as exc:
            raise ToolExecutionError("Division by zero is not allowed") from exc

