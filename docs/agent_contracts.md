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

Phase 2 中 Evaluator 是评分者，负责 rubric 数值、失败维度与通过建议；Critique 是修订教练，消费 EvaluationResult 后解释根因并给出优先修改动作。二者当前只有 Protocol，没有实现或工作流。

