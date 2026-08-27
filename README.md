# Multi-Agent Lesson Planner — Phase 1

这是教程3第一阶段的最小可运行项目。系统用 LangGraph 串联三个 LLM Agent，并用确定性程序节点完成输入标准化、结构校验和落盘：

```text
Input -> Normalize -> Outline Planner -> Writer -> Formatter
      -> Schema Validator -> Save -> Final Lesson Plan
```

## 当前范围

Phase 1 已包含：

- 可替换的模型 Provider、无网络的 `MockModelProvider`，以及 OpenAI/DeepSeek 真实 Provider 适配器；
- 单 Agent、教授—学生双 Agent、Agent 调用 Calculator Tool 三个独立示例；
- Outline Planner、Writer、Formatter 三 Agent 教案流水线；
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

流水线命令打印 `run_id`、状态、校验结果、运行目录和最终文件路径。成功运行的正式教案位于 `runs/<run_id>/final.json`。

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

## 当前配置状态

`config/default.yaml`、`config/models.yaml` 和 `config/evaluation.yaml` 当前是参考/预留文件，Phase 1 运行时尚未加载它们。实际 Provider、model ID、Prompt 版本和 temperature 从本次运行使用的 Provider/Agent 对象写入 `run_meta.json`；Normalize aliases 来自 `run_lesson_pipeline` 的实际参数。只有 `04_lesson_pipeline.py --real` 会显式加载项目 `.env`，其他入口不会隐式加载。`run_meta.json` 会如实记录这些来源，绝不保存 API Key。

## 输出与失败语义

每次运行产生独立目录。成功运行包含：

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

Schema 校验会同时检查详细教学阶段的教师活动、学生活动和评价非空，以及最终 `LessonPlan.task` 与 Normalize 后任务的全部字段一致。校验失败或节点异常时，系统保存 `state.json` 与失败 trace，并停止后续业务处理。失败运行不生成 `final.json`，因此不会把无效结果误认成正式成品。

更详细的非技术复现步骤见 `docs/reproduction.md`。
