**Phase 1 Mock 工程基线验收记录 — 2026-09-16**

结论：修复后，当前 Phase 1 的 Mock 工程基线通过，可以开始增加一个候选 pipeline，并保留本轮基线做回归对照。本结论只证明流程、结构、保存和记录的一致性；真实模型运行尚未验证，教学质量也未评定。

先阅读了 README、复现说明、架构、Agent 契约、数据记录说明、Phase 1 相关代码及全部原有测试，再执行检查。未新增 pipeline、评分规则、迭代流程或界面。

**环境与实际执行**

在项目内创建 `.venv`，使用 Python 3.13.7，安装 `.[dev]`。受限环境中的第一次安装停在构建依赖阶段，终止后通过获准的安装命令完成。没有安装 `.[real]`、读取项目 `.env` 或调用真实模型。测试中的 Provider 适配器使用注入的假客户端和占位凭据，不发出真实请求。样例进程明确移除了 OpenAI/DeepSeek API Key 环境变量。

最终环境为 LangGraph 1.2.11、Pydantic 2.13.5、PyYAML 6.0.3、pytest 9.1.1；`pip check` 通过。完整依赖快照见 [dependencies.txt](../runs/baseline_acceptance/dependencies.txt)。原有 `.pytest_cache` 在受限环境下不可访问，因此检查使用 `runs/baseline_acceptance/` 下的独立缓存与临时目录；没有删除测试或放宽校验。

实际测试记录如下，参数化的每个用例单独计数；各次执行不能相加理解为唯一测试数量：

- 修改前原有测试：22 项通过，失败 0、错误 0、跳过 0。使用机器原有 Python 环境（Pydantic 2.12.5、pytest 9.0.2）。[原始结果](../runs/baseline_acceptance/pytest_initial.xml)
- 首批新增检查、保存修复前：19 项，16 通过、3 失败、跳过 0。三项失败分别复现 final 写入中断、state 写入失败、保存 trace 写入失败。[复现结果](../runs/baseline_acceptance/pytest_before_fix.xml)
- 保存修复后相关检查：26 项通过，失败 0、错误 0、跳过 0。[相关复验](../runs/baseline_acceptance/pytest_related.xml)
- 虚拟环境首次全量检查：41 项通过，失败 0、错误 0、跳过 0。[中间复验](../runs/baseline_acceptance/pytest_final.xml)
- 补查非对象 JSON、输入修复前：实际执行 5 项，5 项失败、跳过 0；另有 19 项因 `-k non_object` 未选中，不是跳过。[输入复现](../runs/baseline_acceptance/pytest_input_before_fix.xml)
- 最终完整测试：**46 项通过，失败 0、错误 0、跳过 0**，包含原有 22 项和新增 24 项。[最终结果](../runs/baseline_acceptance/pytest_verified.xml)

最终测试命令（PowerShell；重复执行时为 `--basetemp` 使用新的验收目录）：

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
Remove-Item Env:OPENAI_API_KEY,Env:DEEPSEEK_API_KEY -ErrorAction SilentlyContinue
& '.venv\Scripts\python.exe' -m pytest -rA -o cache_dir=runs/baseline_acceptance/pytest_cache --basetemp=runs/baseline_acceptance/pytest_verified_tmp --junitxml=runs/baseline_acceptance/pytest_verified.xml
```

**三个样例的最终结果**

均通过仓库原有 `examples/04_lesson_pipeline.py --input ... --mock --runs-dir ...` 入口运行，状态 `completed`，`validation_valid: True`。最终修复前后各执行了一轮三个 CLI 样例，以下为最后一轮的正式验收结果：

- 数学：一元一次方程，七年级。[final.json](../runs/baseline_acceptance/samples/20260916T142302Z_ca2860f7/final.json)
- 科学样例：光合作用，七年级；仓库输入的学科字段实际为“生物”，原样保留。[final.json](../runs/baseline_acceptance/samples/20260916T142303Z_09c8f58b/final.json)
- 语文：说明文的说明方法，八年级。[final.json](../runs/baseline_acceptance/samples/20260916T142303Z_db4d18d5/final.json)

每个链接所在目录都有 10 个文件：`input.json`、`run_meta.json`、`01_normalized.json`、`02_outline_planner.json`、`03_writer.json`、`04_formatter.json`、`05_schema_validation.json`、`state.json`、`trace.jsonl`、`final.json`。每次均依次执行输入标准化、大纲生成、正文撰写、格式整理、结构校验和保存，共六个节点。

已实际逐项校验：中间大纲、正文和最终教案符合现有 Pydantic 模型；最终教案通过现有 `validate_formatted_plan`；任务全部字段与标准化输入一致；每份教案的四个详细环节中教师活动、学生活动、评价均非空；final 与 Formatter 产物、State 内容一致。Trace 的节点顺序、节点类型、成功状态、run_id、相对文件路径、时间、Provider、模型、Prompt 版本和 temperature 与本次执行及元信息一致。程序节点无模型信息，Mock token usage 为 null，未加载 YAML 或 dotenv 的记录如实保留。

还检查了模型调用日志及跨 Agent 实际传递的任务、大纲和正文。同任务重复运行产生独立目录；CLI 样例逐个运行前后对既有产物计算 SHA-256，确认互不覆盖。可复核 [样例检查结果与文件哈希](../runs/baseline_acceptance/sample_verification.json)、[CLI 命令与输出](../runs/baseline_acceptance/sample_cli_logs.json)、[本地检查脚本](../runs/baseline_acceptance/verify_samples.py)。这些只验证工程结构与一致性，不评价教学内容是否适合课堂。

**发现的问题与必要修复**

- 保存失败残留正式结果：原实现先写 final，再写 state/trace，后续失败仍会留下 final；写入 final 中断也可能留下损坏文件。现在 Save 的异常路径移除本次残留 final，保存失败状态，再记录失败 trace。
- Trace 写入失败误报成功：原实现尚未写入 trace 就将 span 标记为结束，导致错误处理再次记录时抛出异常，已保存的完成状态被当作成功返回。现在只在 trace 写入成功后标记结束，写入异常可进入原节点的失败记录路径。
- 非对象 JSON 未留下正确输入记录：`null`、字符串、数字、非空数组可能在建立运行目录前因 `dict(...)` 转换失败；空数组则被错误保存为 `{}`。现在保留原始已解析 JSON，并交由既有 Normalize 拒绝。失败 State 的 `task` 可以保留非法原值，成功 State 与 `LessonTask`/`LessonPlan` 结构保持不变；README 已说明这一失败输入边界。

新增的 24 项验收用例位于 [test_phase1_acceptance.py](../tests/test_phase1_acceptance.py)。原有测试与结构规则均保留；既有模型调用异常、负时长结构失败、任务元信息被改写的测试全部继续通过。

已验证的失败路径包括：缺字段、空白必填字段、字段类型错误、额外字段、非对象 JSON、三个 Agent 各自调用异常、三个详细活动字段为空，以及 final/state/保存 trace 的一次性写入异常。结构校验失败后，Save 仅记录失败状态，不保存正式结果；模型或 Normalize 异常后，不再执行后续业务节点。

最后还逐一读取了最终 pytest 目录中的 **22 个失败运行**：均有 `status: failed`、非空错误、失败 trace，均无 final。[失败运行清单](../runs/baseline_acceptance/failed_runs_verified.json)。修复前的故障复现目录保留作证据，其中存在当时复现的错误 final；它们不是上述最终验收样例。

**未解决的边界与未验证项**

本轮范围内已复现的阻断问题全部修复。以下边界不能据本次验收声称通过：

- 输入文件不存在、无法读取、JSON 文本语法损坏：代码审阅确认在 CLI 入口、Graph 启动前报错，当前不会生成运行 State/trace；本轮未执行这些 CLI 故障场景。若未来要求所有入口错误也具有 run_id 和运行档案，需要另行定义入口失败记录职责。
- 持续磁盘写入/删除失败、trace 写入一半、强制终止、并发压力、崩溃恢复未验证；本轮保存故障测试是一次性异常，并非文件系统事务保证。
- 本轮只验证当前 Windows / Python 3.13.7 环境，未验证 Python 3.11、其他操作系统或所有允许的依赖版本组合。
- 真实模型响应、网络错误、实际 token/费用与真实 Provider 端到端行为未验证；教学正确性、学科适切性和教学质量未评定。

可以开始增加一个候选 pipeline，用同一输入、结构校验、产物检查与失败语义做对照；真实模型验收和教学质量评审仍是后续独立工作。`runs/` 按现有 `.gitignore` 保持为本地验收产物，不会随普通 Git 提交自动纳入版本控制。
