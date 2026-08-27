# Phase 1 Architecture

本实现遵循上层 `设计文档/CODEX_BOOTSTRAP.md` 与 `设计文档/ARCHITECTURE.md` v0.2。当前唯一活动 Graph 是：

```text
START
  -> normalize_input       [program_node]
  -> outline_planner       [llm_agent]
  -> writer                [llm_agent]
  -> formatter             [llm_agent]
  -> schema_validate       [program_node]
  -> save                  [program_node]
  -> END
```

Graph State 只保存 JSON 可序列化值。Agent 的跨节点输出分别由 `LessonOutline`、`LessonDraft`、`LessonPlan` 约束。Outline 使用允许活动细节为空的 `LessonStage`；Writer 和 Formatter 使用要求 `teacher_activity`、`student_activity`、`assessment` 非空的 `DetailedLessonStage`。公共字段 `current_stage`、`errors`、`status`、`run_id` 用于统一运行管理。

Provider 只适配 text、structured output 和 tool call 三类模型调用。Prompt、角色与任务组装属于 Agent；结构限制属于 Pydantic；非空集合和非负时长等确定性规则属于 Schema Validator。

Schema Validator 还逐字段比较最终 `LessonPlan.task` 和 Normalize 后的 `state.task`，Formatter 无权修改任务元数据。Trace 中的 artifact path 一律相对于本次 run 目录。`run_meta` 的模型与 Agent 参数从实际运行对象派生；`config/*.yaml` 在当前阶段未被加载，只是参考/预留文件。

`KnowledgeRetriever` 与 `MockRetriever` 只是接口缝，不含检索实现。`phase2_pipeline.py` 与 `hierarchical.py` 只保存未来契约并主动抛出 `NotImplementedError`，不会被 Phase 1 导入执行。
