import pytest
from pydantic import ValidationError

from lesson_agents.core.schemas import (
    LessonDraft,
    LessonOutline,
    LessonPlan,
    LessonTask,
    TeachingObjective,
)


def test_valid_lesson_task_uses_safe_defaults() -> None:
    task = LessonTask(
        task_id="math_001",
        subject="数学",
        grade="七年级",
        topic="一元一次方程",
    )

    assert task.language == "zh-CN"
    assert task.requirements == []


def test_required_task_field_omission_fails() -> None:
    with pytest.raises(ValidationError):
        LessonTask(task_id="x", subject="数学", grade="七年级")


def test_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        TeachingObjective(category="知识", content="理解概念", score=10)


def test_outline_allows_empty_details_but_draft_and_plan_require_them() -> None:
    objective = {"category": "知识", "content": "理解核心概念"}
    outline_stage = {
        "name": "概念探究",
        "duration_minutes": 10,
        "goal": "建立概念",
        "teacher_activity": None,
        "student_activity": None,
        "assessment": None,
    }
    outline = LessonOutline.model_validate(
        {
            "teaching_objectives": [objective],
            "key_points": ["核心概念"],
            "difficult_points": ["概念迁移"],
            "stages": [outline_stage],
            "strategy_notes": [],
        }
    )
    assert outline.stages[0].teacher_activity is None

    with pytest.raises(ValidationError):
        LessonDraft.model_validate(
            {
                "title": "测试课",
                "overview": "测试完整阶段约束",
                "objectives": [objective],
                "key_points": ["核心概念"],
                "difficult_points": ["概念迁移"],
                "stages": [
                    {
                        **outline_stage,
                        "teacher_activity": "   ",
                        "student_activity": "讨论并作答",
                        "assessment": "观察作答",
                    }
                ],
                "homework": ["练习"],
                "notes": [],
            }
        )

    with pytest.raises(ValidationError):
        LessonPlan.model_validate(
            {
                "task": {
                    "task_id": "x",
                    "subject": "数学",
                    "grade": "七年级",
                    "topic": "方程",
                },
                "title": "测试课",
                "overview": "测试最终教案约束",
                "objectives": [objective],
                "key_points": ["核心概念"],
                "difficult_points": ["概念迁移"],
                "stages": [
                    {
                        **outline_stage,
                        "teacher_activity": "组织探究",
                        "student_activity": "   ",
                        "assessment": "观察作答",
                    }
                ],
                "assessment": ["观察作答"],
                "homework": ["练习"],
            }
        )
