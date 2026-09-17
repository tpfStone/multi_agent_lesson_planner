# 非技术成员复现说明

## 1. 准备环境

安装 Python 3.11 或更高版本，打开项目根目录，在终端执行：

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest
```

看到全部测试通过后再继续。Mock 流程不需要账号、网络或 API Key。

## 2. 准备输入

复制 `data/inputs/math_001.json`，只修改任务 ID、学科、年级、主题、时长和要求。不要删除 `task_id`、`subject`、`grade`、`topic` 四个必填字段。

## 3. 运行 Mock 教案流水线

```bash
python examples/04_lesson_pipeline.py --input data/inputs/math_001.json --mock
```

终端会显示 `status`。`completed` 表示结构校验通过；`failed` 表示本次运行失败。

上述命令默认运行 A。运行候选 B：

```bash
python examples/04_lesson_pipeline.py --input data/inputs/math_001.json --mock --pipeline direct_write
```

比较同一需求时，分别执行 `--pipeline outline_then_write` 和 `--pipeline direct_write`，并可在两条命令中传入相同的 `--comparison-id math-001-pair-1`。每条命令只运行一条完整流程，生成不同的 run_id。默认 Mock 不读取 API Key、不加载 `.env`，不访问网络；它只能验证工程行为。

## 4. 找到结果

终端输出的 `run_dir` 是本次运行目录。成功时，正式结果是其中的 `final.json`。`01_...` 到 `05_...` 是各节点中间产物，`trace.jsonl` 是逐节点执行记录，`state.json` 是最终 State。Trace 的 `artifact_path` 相对于该 run 目录，例如 `03_writer.json`，不会包含开发机器绝对路径。

B 没有 `02_outline_planner.json`，正文为 `03_direct_writer.json`；Formatter 和校验文件名与 A 一致。不要因为文件编号有间隔而认定 B 漏执行；应看 trace 的五节点顺序。

## 5. 识别失败

失败运行没有 `final.json`。打开 `state.json` 查看 `status: failed` 与 `errors`，再打开 `trace.jsonl` 查找 `status: failed` 的节点及其 `error`。系统不会自动重试教案生成；记录写入的一次性故障会尝试保存失败记录。真实 SDK 是否有内部网络重试取决于客户端配置。

若出现 `pipeline_metadata` 失败，即使较早的 Save 事件成功，本次运行仍失败，正式 final 已撤回。`run_meta.json` 会记录最终状态和耗时。Graph 外的文件读取、JSON 文本语法、真实 Provider 初始化错误，以及持续无法写盘等，仍有 README 所述记录边界。

批量核对时检查 `status`、`validation.valid` 和正式文件，不能只看 CLI 退出码，也不能把校验通过当作教学质量结论。

## 6. 可安全标注的文件

数据集整理人员可以复制并标注：

- `input.json`：原始任务；
- `02_outline_planner.json`、`03_writer.json`、`04_formatter.json`：Agent 输出；
- B 对应 `03_direct_writer.json`、`04_formatter.json`，没有独立大纲；
- `05_schema_validation.json`：结构错误与警告；
- `final.json`：仅成功运行存在；
- 另建的人类备注文件。

不要直接改写运行目录里的 `trace.jsonl` 或 `run_meta.json`，否则实验记录会失真。`run_meta.json` 中 `config_files_loaded: []` 表示当前 YAML 配置尚未接入运行时；它不是遗漏。Phase 2 的教学质量分数不能写进 `ValidationResult`。

查看元信息中的 `pipeline_id`、`comparison_id`、输入及标准化任务哈希，核对配对条件；相同 task_id 不保证输入相同。资料快照、提示词哈希、提交号和参数见 [运行记录说明](dataset_schema.md)。旧记录缺少新增字段时保留未知，不人工补造成确定信息。
