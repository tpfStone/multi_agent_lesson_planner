# Dataset and Run Record Schema

建议以一次 run 为一个数据单元，保留以下字段：

| 类别 | 字段 |
|---|---|
| 标识 | task_id, run_id |
| 任务 | subject, grade, topic, duration, requirements, language |
| 模型 | provider, model_id, generation parameters |
| Prompt | outline_planner, writer, formatter 的版本号 |
| 节点输出 | normalized task, outline, draft, formatted plan, validation |
| 运行 | node status, latency, token_usage（可为空）, error |
| 人工标注 | annotator, notes, human scores（另存，不覆盖原产物） |

Phase 2 可在未来追加 `evaluation`、`critique`、`revision_history`、`score`、`approved`、`iteration`，但 Phase 1 不写伪造的评价数据。`token_usage` 或 git commit 无法取得时保持 `null`。

