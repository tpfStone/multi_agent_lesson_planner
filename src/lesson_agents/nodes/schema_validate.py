from __future__ import annotations

from pydantic import ValidationError

from lesson_agents.core.schemas import LessonPlan, LessonTask, ValidationResult
from lesson_agents.core.state import LessonPlanState
from lesson_agents.storage.run_context import RunContext


def validate_formatted_plan(value: object, *, expected_task: object = None) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        plan = LessonPlan.model_validate(value)
    except ValidationError as exc:
        for item in exc.errors(include_url=False):
            location = ".".join(str(part) for part in item["loc"])
            errors.append(f"{location}: {item['msg']}")
        return ValidationResult(valid=False, errors=errors, warnings=warnings)

    try:
        normalized_task = LessonTask.model_validate(expected_task)
    except ValidationError as exc:
        errors.append(f"state.task is invalid: {exc.errors(include_url=False)}")
    else:
        for field_name in LessonTask.model_fields:
            expected_value = getattr(normalized_task, field_name)
            actual_value = getattr(plan.task, field_name)
            if actual_value != expected_value:
                errors.append(
                    f"task.{field_name} must match normalized state.task "
                    f"(expected {expected_value!r}, got {actual_value!r})"
                )

    required_collections = {
        "objectives": plan.objectives,
        "key_points": plan.key_points,
        "difficult_points": plan.difficult_points,
        "stages": plan.stages,
        "assessment": plan.assessment,
        "homework": plan.homework,
    }
    for name, collection in required_collections.items():
        if not collection:
            errors.append(f"{name} must not be empty")

    for index, stage in enumerate(plan.stages):
        if stage.duration_minutes is not None and stage.duration_minutes < 0:
            errors.append(f"stages.{index}.duration_minutes must be non-negative")
        if stage.duration_minutes is None:
            warnings.append(f"stages.{index}.duration_minutes is not provided")

    return ValidationResult(valid=not errors, errors=errors, warnings=warnings)


def make_schema_validate_node(context: RunContext):
    def schema_validate(state: LessonPlanState) -> dict:
        span = context.traces.start_span(node="schema_validate", node_type="program_node")
        try:
            result = validate_formatted_plan(
                state.get("formatted_plan"),
                expected_task=state.get("task"),
            )
            existing_errors = list(state.get("errors", []))
            update = {
                "validation": result.model_dump(mode="json"),
                "current_stage": "validated" if result.valid else "validation_failed",
                "errors": existing_errors + result.errors,
                "status": "running" if result.valid else "failed",
            }
            artifact = context.artifacts.save_json(
                "05_schema_validation.json", result.model_dump(mode="json")
            )
            context.capture(state, update)
            span.finish(
                status="success" if result.valid else "failed",
                artifact_path=artifact,
                error=None if result.valid else "; ".join(result.errors),
            )
            return update
        except Exception as exc:
            span.finish(status="failed", artifact_path=None, error=str(exc))
            context.persist_failure(state, node="schema_validate", error=exc)
            raise

    return schema_validate
