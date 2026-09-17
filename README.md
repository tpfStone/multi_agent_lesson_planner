# Multi-Agent Lesson Planner — Phase 1

这是教程3第一阶段的最小可运行项目。系统提供两条完整教案流程，由 LangGraph 串联 LLM Agent，并用确定性程序节点完成输入标准化、结构校验和落盘。默认基线 A：

```text
Input -> Normalize -> Outline Planner -> Writer -> Formatter
      -> Schema Validator -> Save -> Final Lesson Plan
```

候选 B（`direct_write`）直接从任务撰写正文：

```text
Input -> Normalize -> Direct Writer -> Formatter
      -> Schema Validator -> Save -> Final Lesson Plan
```

## 当前范围

Phase 1 已包含：

- 可替换的模型 Provider、无网络的 `MockModelProvider`，以及 OpenAI/DeepSeek 真实 Provider 适配器；
- 单 Agent、教授—学生双 Agent、Agent 调用 Calculator Tool 三个独立示例；
- 默认 A 的 Outline Planner、Writer、Formatter，以及可手动选择的 B 的 Direct Writer、Formatter；
- JSON artifacts、JSONL trace、Pydantic 结构校验和失败 State；
- 无 API Key 的 pytest 与 Mock E2E。

明确不包含：真实 RAG、向量库、教学质量 Evaluator、Critique 修订循环、Hierarchical 调度、Web UI 和数据库。Phase 2 文件仅为接口或占位。

## 安装

要求 Python 3.11+。在项目根目录执行：

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
```

如需手工运行真实 Provider，再安装可选依赖：

```bash
python -m pip install -e ".[real]"
```

## 首先运行 Mock

Mock 不读取 API Key，也不访问网络：

```bash
python -m pytest
python examples/01_single_agent.py --mock
python examples/02_two_agent_chat.py --mock
python examples/03_agent_tool_call.py --mock
python examples/04_lesson_pipeline.py --input data/inputs/math_001.json --mock
```

流水线命令打印 `run_id`、流程、状态、校验结果、运行目录和最终文件路径。成功运行的正式教案位于 `runs/<run_id>/final.json`。

运行 B：

```bash
python examples/04_lesson_pipeline.py --input data/inputs/math_001.json --mock --pipeline direct_write
```

给同一输入分别运行 A、B，可用相同的 `--comparison-id` 关联，但每条流程仍独立执行并建立自己的目录：

```bash
python examples/04_lesson_pipeline.py --input data/inputs/math_001.json --mock --pipeline outline_then_write --comparison-id math-001-pair-1
python examples/04_lesson_pipeline.py --input data/inputs/math_001.json --mock --pipeline direct_write --comparison-id math-001-pair-1
```

Python 入口为 `run_lesson_pipeline(raw_task, pipeline="direct_write", comparison_id="math-001-pair-1")`；省略 `pipeline` 仍为 A。未知流程会在建立运行目录和调用模型前报错。B 不运行大纲节点，也不读取 A 的中间产物。Mock 内容仅用于工程验证，不能用其内容或耗时判断教学质量与真实模型成本。

## 手工运行真实模型

只有在 Mock E2E 通过后才进行本步骤。复制 `.env.example` 为项目根目录 `.env`，填写可用的模型 ID 与密钥。`examples/04_lesson_pipeline.py --real` 会显式加载该文件，但 `OpenAIModelProvider` 本身仍只读取环境变量。

PowerShell 示例：

```powershell
$env:OPENAI_API_KEY = "your-key"
$env:LESSON_MODEL_ID = "your-available-model-id"
python examples/04_lesson_pipeline.py --input data/inputs/math_001.json --real
```

DeepSeek 示例 `.env`：

```dotenv
LESSON_PROVIDER=deepseek
LESSON_MODEL_ID=deepseek-v4-flash
DEEPSEEK_API_KEY=your-key
```

为兼容已有环境，DeepSeek Provider 在未设置 `DEEPSEEK_API_KEY` 时也接受 `OPENAI_API_KEY`。其官方 Base URL 由 Provider 固定为 `https://api.deepseek.com`。

真实 smoke test 应依次运行 `math_001.json`、`science_001.json`、`chinese_001.json`。这属于人工验收，不进入单元测试，也不能把 Schema 通过解释为教学质量优秀。

两条流程使用同一 `--real` 入口和 Provider 适配器，以 `--pipeline` 选择。当前 B 的验收为无网络工程验收，尚未执行真实模型比较。

## 当前配置状态

`config/default.yaml`、`config/models.yaml` 和 `config/evaluation.yaml` 当前是参考/预留文件，Phase 1 运行时尚未加载它们。实际 Provider、model ID、Prompt 版本和 temperature 从本次运行使用的 Provider/Agent 对象写入 `run_meta.json`；Normalize aliases 来自 `run_lesson_pipeline` 的实际参数。只有 `04_lesson_pipeline.py --real` 会显式加载项目 `.env`，其他入口不会隐式加载。`run_meta.json` 会如实记录这些来源，绝不保存 API Key。

运行记录还包含流程名与版本、比较标识、输入/标准化任务哈希、实际提交与工作区状态、提示词哈希、依赖版本、实际资料快照及端到端耗时。Git 无法取得的信息保留未知。默认资料为空；真实 Retriever 尚未实现。字段及计时边界见 [运行记录说明](docs/dataset_schema.md)。

## 输出与失败语义

每次运行产生独立目录。A 成功运行包含：

```text
input.json
run_meta.json
01_normalized.json
02_outline_planner.json
03_writer.json
04_formatter.json
05_schema_validation.json
state.json
trace.jsonl
final.json
```

B 使用 `03_direct_writer.json` 替代 `03_writer.json`，省略 `02_outline_planner.json`，其余文件名不变。编号不连续是有意保留的兼容命名，实际顺序以 trace 为准。

Schema 校验会同时检查详细教学阶段的教师活动、学生活动和评价非空，以及最终 `LessonPlan.task` 与 Normalize 后任务的全部字段一致。校验失败或节点异常时，系统保存 `state.json` 与失败 trace，并停止后续业务处理。失败运行不生成 `final.json`，因此不会把无效结果误认成正式成品。

已解析的 JSON 若顶层不是对象，也会在 Normalize 节点被拒绝，并原样保留在 `input.json` 和失败 State 的 `task` 中；成功 State 的 `task` 仍是标准化后的任务对象。保存节点写入 final、state 或 trace 时若发生可恢复异常，会移除本次残留的 `final.json` 并记录失败。输入文件读取/JSON 语法错误发生在命令行入口，尚不属于 Graph 运行记录；持续无法写入磁盘或进程被强制终止时，也不保证记录完整。

最终元信息写入也是完成条件。若 Save 后写入元信息失败，系统会撤回 final，追加 `pipeline_metadata` 失败事件并更新失败记录；此时之前的 Save 成功事件不代表整条运行成功。可恢复的记录写入故障会尝试落盘失败记录，不会重新调用模型。CLI 保持既有退出码行为，自动检查应读取运行状态和校验结果，不能仅看进程退出码。

更详细的步骤见 [复现说明](docs/reproduction.md)，本次实现依据见 [候选 B 计划](docs/implementation_plans/candidate-b-direct-writing-plan.md)，实际测试和限制见 [候选 B 验收记录](docs/candidate_b_acceptance.md)。
