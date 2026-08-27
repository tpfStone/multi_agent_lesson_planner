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

## 4. 找到结果

终端输出的 `run_dir` 是本次运行目录。成功时，正式结果是其中的 `final.json`。`01_...` 到 `05_...` 是各节点中间产物，`trace.jsonl` 是逐节点执行记录，`state.json` 是最终 State。Trace 的 `artifact_path` 相对于该 run 目录，例如 `03_writer.json`，不会包含开发机器绝对路径。

## 5. 识别失败

失败运行没有 `final.json`。打开 `state.json` 查看 `status: failed` 与 `errors`，再打开 `trace.jsonl` 查找 `status: failed` 的节点及其 `error`。系统当前不会自动重试。

## 6. 可安全标注的文件

数据集整理人员可以复制并标注：

- `input.json`：原始任务；
- `02_outline_planner.json`、`03_writer.json`、`04_formatter.json`：Agent 输出；
- `05_schema_validation.json`：结构错误与警告；
- `final.json`：仅成功运行存在；
- 另建的人类备注文件。

不要直接改写运行目录里的 `trace.jsonl` 或 `run_meta.json`，否则实验记录会失真。`run_meta.json` 中 `config_files_loaded: []` 表示当前 YAML 配置尚未接入运行时；它不是遗漏。Phase 2 的教学质量分数不能写进 `ValidationResult`。
