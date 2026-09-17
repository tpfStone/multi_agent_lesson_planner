# 候选 B 工程验收记录 — 2026-09-17

候选 B（`direct_write`）已完成工程实现和无网络 Mock 验收，默认 A（`outline_then_write`）保持原有生成行为。真实模型运行、真实成本/时延和教学质量未验收。

实施依据为 [候选 B 计划](implementation_plans/candidate-b-direct-writing-plan.md)。行为基线为 `b9dcded7e74d6b63e7b4b9c9f78e37ea7378bf02`；验收在本次实现提交前执行，针对该基线上的工作区修改。样例元信息保留验收当时的真实 HEAD 和 `git_dirty: true`，不会在后续提交时改写历史记录；包版本仍为 `0.1.0`。

## 已交付行为

- Python 与 CLI 可选择 A/B；默认 A，未知流程在初始化前拒绝，可用 comparison_id 关联独立运行。
- B 依次执行 Normalize、DirectWriter、Formatter、Validator、Save；只进行 Draft、Plan 两次 Agent 调用，不执行大纲步骤。
- DirectWriter 使用独立提示词、`0.2` temperature 和现有 `LessonDraft`；公共 Formatter 已提取，两条流程使用相同后处理。
- B 正文为 `03_direct_writer.json`，没有大纲文件。A 仍为原 10 个文件，B 成功运行为 9 个文件。
- 增加流程/记录版本、原始与标准化输入哈希、实际提交与工作区状态、提示词哈希、依赖环境、请求配置来源、资料快照及端到端耗时。
- 资料快照在模型调用前持久化。默认空资料；固定资料测试通过既有 Retriever 接口注入，没有实现真实检索。
- 初始、标准化、资料记录或终态元信息写入的一次性故障均不会伪装成成功。Save 后终态元信息写入失败会撤回 final，并追加 pipeline_metadata 失败事件。
- 保留原有输入、模型、校验和保存失败语义，没有增加生成重试、自动修复、回退 A 或教学评分。

## 环境与测试证据

使用项目已有 `.venv`，Windows / Python 3.13.7，LangGraph 1.2.11、Pydantic 2.13.5、PyYAML 6.0.3、pytest 9.1.1。没有安装或调用真实模型 SDK；Provider 测试使用假客户端/假模块。`pip check` 通过。完整环境见 [依赖快照](../runs/candidate_b_acceptance_20260917_155745/dependencies.txt)。其中 editable 项的提交号不包含未提交修改，不能替代本记录对工作区状态的说明。

各次执行分别计数，不能相加理解为唯一测试数：

- 开发前基线复验：46 项通过，0 失败、0 错误、0 跳过。[baseline.xml](../runs/candidate_b_acceptance_20260917_155745/baseline.xml)
- 主路径和记录接入后，原有测试回归：46 项通过。[regression.xml](../runs/candidate_b_acceptance_20260917_155745/regression.xml)
- 最终完整测试：**91 项通过，0 失败、0 错误、0 跳过**，耗时 18.55 秒；包括原有 46 项和新增 45 项。[implementation.xml](../runs/candidate_b_acceptance_20260917_155745/implementation.xml)

新增覆盖见 [B 验收测试](../tests/test_direct_write_pipeline.py)和 [Provider 测试](../tests/test_provider.py)。包括三种学科、A 默认/显式选择一致性、跨流程独立目录、未知流程、非法输入、各模型节点异常、直接正文缺失/空白细节、最终任务改写/负时长、final/state/trace 保存故障、两条流程四个阶段的元信息故障、资料调用前留档、检索失败、输入哈希、Git 不可用及请求配置来源。

实际最终测试命令如下，重跑需为 basetemp 和报告使用新路径，以保留本次证据：

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONIOENCODING='utf-8'
Remove-Item Env:OPENAI_API_KEY,Env:DEEPSEEK_API_KEY -ErrorAction SilentlyContinue
& '.venv/Scripts/python.exe' -m pytest -rA -o cache_dir=runs/candidate_b_acceptance_20260917_155745/pytest_cache --basetemp=runs/candidate_b_acceptance_20260917_155745/implementation_tmp --junitxml=runs/candidate_b_acceptance_20260917_155745/implementation.xml
```

## CLI 与基线兼容检查

通过现有 `examples/04_lesson_pipeline.py --mock` 入口，为三个输入分别运行 A、B，共六次成功，均为 completed、结构校验有效、独立 run_id。

- 数学：A [结果](../runs/candidate_b_acceptance_20260917_155745/samples/20260917T081422Z_8b77f5ea/final.json)，B [结果](../runs/candidate_b_acceptance_20260917_155745/samples/20260917T081423Z_8495366a/final.json)。
- 生物（输入文件名 science）：A [结果](../runs/candidate_b_acceptance_20260917_155745/samples/20260917T081424Z_e0a5479a/final.json)，B [结果](../runs/candidate_b_acceptance_20260917_155745/samples/20260917T081425Z_48109842/final.json)。
- 语文：A [结果](../runs/candidate_b_acceptance_20260917_155745/samples/20260917T081426Z_1f1d8e32/final.json)，B [结果](../runs/candidate_b_acceptance_20260917_155745/samples/20260917T081427Z_7ac4c50c/final.json)。

逐项核对了文件集合、Schema、任务一致性、State/final/Formatter 一致性、trace 顺序、空资料记录、模型调用节点数、输入哈希、配对标识以及 Git 修改状态；通过文件 SHA-256 确认后续运行未覆盖既有样例。

证据包含 [检查脚本](../runs/candidate_b_acceptance_20260917_155745/verify_cli.py)、[命令与输出](../runs/candidate_b_acceptance_20260917_155745/sample_cli_logs.json)、[核对结果与文件哈希](../runs/candidate_b_acceptance_20260917_155745/sample_verification.json)。该本地脚本拒绝覆盖已存在的 samples 目录，重跑应另设验收目录。

另对照开发前 pytest 留下的 A 产物，确认三个相同样例的 input、normalized、outline、draft、formatted plan、validation、final 均与新 CLI A 结果相同。与 HEAD 比较，原三份提示词、Schema、State、Validator、Save 共 7 个文件内容未改；原有 35 个测试/辅助函数的 AST 保持一致（参数化后为原 46 项测试）。参见 [兼容检查脚本](../runs/candidate_b_acceptance_20260917_155745/audit_compatibility.py)和 [检查结果、源码哈希](../runs/candidate_b_acceptance_20260917_155745/compatibility_audit.json)。

## 实施取舍与未验证边界

按计划使用显式双流程分派和现有 Schema，没有增加通用框架。元信息内嵌小规模资料快照，以保留 A/B 的既定文件集合。旧记录兼容以增量字段和文档契约处理，本次没有新增历史读取器或迁移工具。

终态元信息由应用层在 Graph 返回或失败后完成，因此最后写入故障增加的是 pipeline_metadata 失败 trace，而非正常 Graph 节点。elapsed_ms 覆盖初始化、Graph 和既定失败处理，排除最后一次元信息写入及函数返回；不能当作纯推理耗时。详情见 [记录格式](dataset_schema.md)。

- 当前环境读取用户全局 Git ignore 文件有权限警告；已观察到工作区修改，因此记录 dirty 为 true，并附 git_status_reported_warnings。代码对无法确认干净的情况保留未知，不因 Git 信息缺失阻断生成。
- 未读取项目 `.env`、调用真实模型或执行真实检索；无法据本轮确定实际请求重试、用量、费用、速度或教学优劣。
- 只验证了当前 Windows/Python 环境，没有验证其他系统或所有允许的依赖版本组合。
- 文件故障验收为可恢复的一次性异常，不保证持续写入/删除失败、半截 trace、强制终止或崩溃恢复。
- CLI 对 Graph 失败仍保持既有退出码行为；调用方须读取运行 status、校验与产物。Graph 外入口错误仍不保证完整运行档案。
- 没有开发候选 C/D、反馈修订、质量评分或批量实验平台。

`runs/` 继续按 `.gitignore` 作为本地验收证据，不随普通 Git 提交自动保存。若需他人复核，应另行保存该目录或重新执行验收；上面的本地证据链接仅在保留这些文件的工作区有效。
