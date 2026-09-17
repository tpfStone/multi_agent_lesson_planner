# Agent and Node Contracts

| 组件 | 类型 | 输入 | 输出 | 不负责 |
|---|---|---|---|---|
| Outline Planner | LLM Agent | LessonTask + optional knowledge | LessonOutline | 完整正文、质量评分 |
| Writer | LLM Agent | LessonTask + LessonOutline + optional knowledge | LessonDraft | 重做大纲、最终格式、评分 |
| Formatter | LLM Agent | LessonDraft + 只读任务元数据 | LessonPlan | 教学质量评价、删减必填内容 |
| Normalize | Program Node | 原始 JSON | LessonTask dict | 猜测缺失字段、模型调用 |
| Schema Validator | Program Node | formatted plan | ValidationResult | 判断教学质量 |
| Save | Program Node | State + validation | state/final artifacts | 修改教案内容、模型调用 |

Calculator Agent 是任务书 Step 2 的独立演示，不是主 Graph 节点。它要求模型返回一个明确的 ToolCall，再由 Agent 校验工具名并把参数分派给安全 CalculatorTool；工具实现不使用 `eval`。

候选 B 的 `DirectWriterAgent` 输入为 `LessonTask + optional knowledge`，输出为 `LessonDraft`。它一次完成目标、重难点、详细教学活动、作业等正文内容，不接收或生成独立大纲，不生成质量分数。temperature 为 `0.2`，提示词为 `direct_writer_v1`。原 Writer 的大纲输入仍为必需，职责未改变。

A、B 共用 Formatter（`formatter_v1`、temperature `0.0`）以及 Normalize、Validator、Save。B 无 `outline` State 字段或大纲产物。每次运行独立创建 Agent/节点及上下文，不共享可变 State 或消耗过的 Mock 队列。

资料快照由 RunContext 记录，模型调用与检索失败沿用停止后续业务处理的规则；格式整理不是自动修复失败正文的后备路径。运行控制字段 `pipeline`、`comparison_id` 不进入 `LessonTask`。

Phase 2 中 Evaluator 是评分者，负责 rubric 数值、失败维度与通过建议；Critique 是修订教练，消费 EvaluationResult 后解释根因并给出优先修改动作。二者当前只有 Protocol，没有实现或工作流。

这两项 Protocol 当前接收 `LessonPlan`，不能直接插入只持有 `LessonDraft` 的格式整理前位置。进入修订研究时需重新明确评价对象；现有评分维度和阈值不作为正式教学评价标准。
