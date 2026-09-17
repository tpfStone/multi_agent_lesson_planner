# Phase 1 Architecture

本实现基于上层 `设计文档/CODEX_BOOTSTRAP.md` 与 `设计文档/ARCHITECTURE.md` v0.2，并按 [候选 B 计划](implementation_plans/candidate-b-direct-writing-plan.md)增加直接撰写流程。默认活动 Graph A（`outline_then_write`）为：

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

候选 B（`direct_write`）为：

```text
START -> normalize_input -> direct_writer -> formatter -> schema_validate -> save -> END
```

`run_lesson_pipeline` 显式选择两个构建函数之一，默认 A，未知流程在初始化前拒绝。B 的 `DirectWriterAgent` 从任务与资料直接生成 `LessonDraft`，没有大纲节点或占位大纲。两条流程分别创建 State、RunContext 和 run 目录，共用 Normalize、Formatter、Validator、Save 的节点工厂；Formatter 的包装位于 `nodes/formatter.py`。A 原有六节点顺序、提示词及产物名称保持不变。

Graph State 只保存 JSON 可序列化值。Agent 的跨节点输出分别由 `LessonOutline`、`LessonDraft`、`LessonPlan` 约束。Outline 使用允许活动细节为空的 `LessonStage`；Writer 和 Formatter 使用要求 `teacher_activity`、`student_activity`、`assessment` 非空的 `DetailedLessonStage`。公共字段 `current_stage`、`errors`、`status`、`run_id` 用于统一运行管理。

Provider 只适配 text、structured output 和 tool call 三类模型调用。Prompt、角色与任务组装属于 Agent；结构限制属于 Pydantic；非空集合和非负时长等确定性规则属于 Schema Validator。

Schema Validator 还逐字段比较最终 `LessonPlan.task` 和 Normalize 后的 `state.task`，Formatter 无权修改任务元数据。Trace 中的 artifact path 一律相对于本次 run 目录。`run_meta` 的模型与 Agent 参数从实际运行对象派生；`config/*.yaml` 在当前阶段未被加载，只是参考/预留文件。

`KnowledgeRetriever` 与 `MockRetriever` 只是接口缝，不含检索实现。`phase2_pipeline.py` 与 `hierarchical.py` 只保存未来契约并主动抛出 `NotImplementedError`，不会被 Phase 1 导入执行。

RunContext 在模型调用前把实际检索请求与资料快照写入 `run_meta.json`，区分未调用、已取得资料（可为空）和检索失败。A 保留大纲、正文各一次检索；B 使用同一正文查询规则进行一次检索。记录不改变模型 payload，也不把 Formatter 生成的 sources 当作检索证据。

应用入口补充流程/提示词版本、输入哈希、代码来源、依赖环境和运行计时，并在 Graph 结束或失败后写入终态元信息。终态元信息写入失败时，撤回正式 final，保存失败 State 与 `pipeline_metadata` 失败 trace；正常路径不增加 Graph 节点。Git 元信息不可得保留未知，持续磁盘故障或强制终止不保证恢复。

未来 C、D 可以在生成 `LessonDraft` 后接入公共后处理。反馈修订需先解决 Evaluator/Critique 当前接收 `LessonPlan`、而计划反馈位置只有 Draft 的契约差异；本次不激活占位评分和循环。
