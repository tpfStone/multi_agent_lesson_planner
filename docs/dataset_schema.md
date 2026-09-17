# Dataset and Run Record Schema

一次 run 是一个独立数据单元。`input.json` 保留原始已解析 JSON；Normalize 成功验证后的任务保存在 `01_normalized.json`。任务结构仍为 task_id、subject、grade、topic、duration、requirements、language，不含运行控制字段。

## 流程和产物

- A：`pipeline_id: outline_then_write`、`pipeline_version: "1"`，大纲 `02_outline_planner.json`，正文 `03_writer.json`。
- B：`pipeline_id: direct_write`、`pipeline_version: "1"`，正文 `03_direct_writer.json`，无大纲字段或文件。
- 两条流程共用 `04_formatter.json`、`05_schema_validation.json`、`state.json`、`trace.jsonl`、`final.json` 名称。实际执行顺序以 trace 为准。
- `final.json` 仅作为完整成功运行的正式结果；结构校验通过还不足以判定保存及最终记录成功。

## run_meta.json：格式版本 1

原有字段继续保留，新增字段不回填历史目录。

- `metadata_schema_version`：当前为整数 `1`；旧文件没有该字段。
- `run_id`、`created_at`：独立运行标识和元信息初始化 UTC 时间；created_at 不是精确的函数入口时间。
- `pipeline_id`、`pipeline_version`：所选流程与行为版本；不等同于包版本或 Git 提交。
- `comparison_id`：可选的调用方配对标识，默认 `null`。相同标识不自动证明条件一致，也不自动执行另一条流程。
- `input_hash`：原始已解析 JSON 值的 SHA-256；`normalized_task_hash`：任务通过 Normalize 验证后的哈希，未取得时为 `null`。
- `hash_serialization`：JSON 以 `ensure_ascii=False`、`sort_keys=True`、`separators=(',', ':')` 序列化，再对 UTF-8 字节做 SHA-256。保持数组顺序和字符串内容，键顺序不影响哈希；不是源文件字节哈希，也不证明教学语义相等。
- `code_version`：包版本。`git_commit`：执行代码所在仓库的 HEAD，不能硬填行为基线提交。
- `git_dirty`：源仓库有已跟踪或未忽略的未跟踪修改时为 true；完整检查确认干净时为 false；无法确定时为 `null`。忽略的 runs 等文件不计入。
- `git_notes`：Git 不可用或 status 有警告等原因代码，不保存命令 stderr 中的本机路径。若警告下已经看见修改，可确认 dirty；未看到修改但存在警告时不能宣称干净。非 Git 源目录保留未知。
- `environment`：Python 版本以及 langgraph、pydantic、PyYAML、openai 的已安装版本；未安装包为 `null`。这不是完整依赖锁文件，正式比较仍应保存依赖快照。
- `provider`、`model_id`、`base_url`、`prompt_versions`、`generation_parameters`：继续从实际对象派生。model_id 是配置 ID，不保证是服务端解析别名后的精确模型版本。
- `prompt_hashes`：各参与 Agent 实际加载的 system 模板文本（经过既有 load_prompt 的 strip）的 UTF-8 SHA-256。Provider 注入的 Schema 等适配逻辑由代码版本追溯，不能把模板哈希理解成整份 HTTP 请求哈希。
- `runtime_parameters.normalization_aliases`：实际 aliases。输入哈希一致时仍需核对它与标准化任务。
- `configuration`、`config_version`：保留已有来源含义；当前 `config_files_loaded` 为 `[]`、`config_version` 为 `null`，不伪称加载 YAML。

B 的 Agent 元信息仅含 direct_writer 与 formatter。元信息描述所配置的流程；实际执行到哪些节点、哪些请求成功，应结合 trace 判断。

## 请求配置与实际资料

`request_configuration` 说明已知的请求配置来源：

- Mock 标明无网络请求，timeout、max_retries、output_token_limit 为不适用的 `null`。
- 当前真实适配器没有显式设置超时、重试或输出上限。普通构造标为 `sdk_defaults`，注入客户端标为 `injected_client_configuration`；输出上限按适配器未指定、服务端默认记录，不臆造数值。
- 自定义 Provider 不暴露此信息时标为 provider_defined/未知。现有 ModelProvider Protocol 不要求增加方法。

`knowledge` 按使用资料的节点记录。A 包含 outline_planner、writer，B 只包含 direct_writer：

- `status: not_called`：节点尚未获取资料，request/documents/snapshot_hash/error 均为空。
- `status: retrieved`：记录实际 request（subject、grade、topic、query）、documents 和 snapshot_hash。空资料为 `documents: []`，有确定哈希，不能视为未知。
- `status: failed`：获取或准备快照失败，保留 request 和 error；没有取得资料时 documents/hash 为 `null`。
- documents 保留 Retriever 返回的 JSON 资料及其自带的来源、版本字段，不补造来源。snapshot_hash 使用上述稳定 JSON 哈希规则。
- 快照在模型调用前写入，因此模型异常后仍可核对其输入资料。元信息写入故障本身仍会令节点失败；status 为 retrieved 仅说明已获取资料，不证明模型已调用。

默认 MockRetriever 返回空资料。非空固定资料通过 Python 入口的 retriever 注入，当前未实现真实 RAG；最终 `LessonPlan.sources` 不是实际检索档案的替代品。

## 状态、计时与用量

`run_meta.status` 初始为 running，结束时为 completed 或 failed。`elapsed_ms` 在终态记录，使用 perf_counter；计时从流程选择验证后、Provider/运行目录初始化前开始，到 Graph 完成或失败处理后、最后一次 run_meta 写入前结束。最后一次元信息写入与函数返回不计入，其范围在 `timing_scope` 中说明。记录写入失败后转入失败处理时重新取得终态耗时。

节点 trace 保留 node、node_type、status、iteration（当前恒为 0）、started_at、ended_at、latency_ms、artifact_path、provider、model_id、prompt_version、temperature、token_usage、error。artifact_path 是 run 内相对路径；程序节点没有模型信息。latency_ms 包括节点内检索、模型及部分落盘耗时，不是纯推理时间。端到端耗时不由节点求和得到。

正常 A 为六个节点、三次 Agent 调用，B 为五个节点、两次 Agent 调用；SDK 内部重试可能令实际 HTTP 请求数更多。token_usage 不可得时仍为 `null`，尤其失败调用不能假定免费。当前不生成总用量或费用估算；后续汇总必须标明缺失。

Graph 建立或初始元信息失败可产生 `pipeline` 程序失败事件。Save 后的终态元信息写入失败会追加 `pipeline_metadata` 失败事件、撤回 final 并更新失败 State；此时应按整条运行最终状态判断，而不能只看之前 Save 的成功事件。持续写盘/删除失败及进程中断不保证档案完整。

## 历史记录与人工评价

读取旧记录时允许新增字段缺失，保留为历史缺失/未知；不要把未知填成零用量、成功状态或确定的 A 身份。流程推断若有需要，应结合来源和实际节点/产物。当前没有新增历史记录迁移器或读取平台。

人工标注的 annotator、notes、human scores 另存，不覆盖原始产物。Schema 通过不是教学质量结论。Phase 2 的 evaluation、critique、revision_history、score、approved 等字段仍未实现，不写伪造值；进入修订研究后再定义修订血缘与多轮产物。
