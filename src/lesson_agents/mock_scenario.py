from __future__ import annotations

from copy import deepcopy

from lesson_agents.core.schemas import LessonTask
from lesson_agents.models.mock import MockModelProvider, ScriptedStructuredResponse


def build_mock_phase1_provider(
    task: LessonTask,
    *,
    invalid_final_duration: bool = False,
    final_task_overrides: dict | None = None,
) -> MockModelProvider:
    """Build deterministic domain fixtures for the three Phase 1 agent calls."""

    objectives = [
        {"category": "知识与技能", "content": f"理解并掌握{task.topic}的核心概念与基本方法"},
        {"category": "过程与方法", "content": f"通过观察、讨论和练习解决与{task.topic}有关的问题"},
        {"category": "情感与态度", "content": "在合作交流中形成严谨表达和主动检验的习惯"},
    ]
    outline_stages = [
        {
            "name": "情境导入",
            "duration_minutes": 5,
            "goal": "激活已有经验并提出本课问题",
            "teacher_activity": None,
            "student_activity": None,
            "assessment": None,
        },
        {
            "name": "概念探究",
            "duration_minutes": 12,
            "goal": f"建立{task.topic}的核心认识",
            "teacher_activity": None,
            "student_activity": None,
            "assessment": None,
        },
        {
            "name": "例题与练习",
            "duration_minutes": 20,
            "goal": "应用方法并解释解题过程",
            "teacher_activity": None,
            "student_activity": None,
            "assessment": None,
        },
        {
            "name": "总结与迁移",
            "duration_minutes": 8,
            "goal": "梳理方法并迁移到新情境",
            "teacher_activity": None,
            "student_activity": None,
            "assessment": None,
        },
    ]
    outline = {
        "teaching_objectives": objectives,
        "key_points": [f"{task.topic}的核心概念", "基本方法的规范使用"],
        "difficult_points": ["把实际问题转化为清晰的思考步骤"],
        "stages": outline_stages,
        "strategy_notes": ["用问题链组织探究", "通过即时反馈检查理解"],
    }

    detailed_stages: list[dict] = []
    for stage in outline_stages:
        detailed = deepcopy(stage)
        detailed["teacher_activity"] = f"围绕“{stage['goal']}”提出问题、示范方法并组织反馈。"
        detailed["student_activity"] = "独立思考后与同伴交流，展示过程并根据反馈修正。"
        detailed["assessment"] = "通过提问、观察学习单和代表性作答进行形成性检查。"
        detailed_stages.append(detailed)

    draft = {
        "title": f"{task.grade}{task.subject}：{task.topic}",
        "overview": f"本课面向{task.grade}学生，通过问题情境、探究与练习学习{task.topic}。",
        "objectives": objectives,
        "key_points": outline["key_points"],
        "difficult_points": outline["difficult_points"],
        "stages": detailed_stages,
        "homework": [f"完成一组有关{task.topic}的基础与迁移练习", "写出一道易错题的订正说明"],
        "notes": ["根据课堂反馈调整练习数量"],
    }
    plan = {
        "task": task.model_dump(mode="json"),
        "title": draft["title"],
        "overview": draft["overview"],
        "objectives": objectives,
        "key_points": draft["key_points"],
        "difficult_points": draft["difficult_points"],
        "stages": detailed_stages,
        "assessment": [stage["assessment"] for stage in detailed_stages],
        "homework": draft["homework"],
        "notes": draft["notes"],
        "sources": [],
    }
    if invalid_final_duration:
        plan["stages"][0]["duration_minutes"] = -1
    if final_task_overrides:
        plan["task"].update(final_task_overrides)
    return MockModelProvider(
        structured_responses=[
            ScriptedStructuredResponse("LessonOutline", outline),
            ScriptedStructuredResponse("LessonDraft", draft),
            ScriptedStructuredResponse("LessonPlan", plan),
        ]
    )
