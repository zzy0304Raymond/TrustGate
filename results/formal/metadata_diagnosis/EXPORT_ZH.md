# 给实验 2、3、4、5 的组员

这次只需交 **一个 JSON 检查文件**，不用重跑实验，不用 API，也不用上传原始请求、完整状态或密钥。

1. 获取包含 `scripts/formal/extract_metadata_trace_checks.py` 的代码版本，保留原实验目录，使用原来 Python 3.10.20 的依赖环境。不要改冻结算法、结果或运行凭据。
2. 找到本人原始分片目录：其中应有 `results.json` 及各案例子目录；案例目录内有 `summary.json`、逐轮 `request_*.json` / `response_*.json`、`trajectory.json`、`tool_calls.json`、`defense_events.json`、`api_usage.json`、`raw_tools.json` 和 `environment_before.json` / `environment_after.json`。公开的 `results.csv` 或摘录不能代替这些原件。
3. 在仓库根目录执行下面的命令。把人员编号、目录路径和输出文件名换成自己的；无需手动挑选案例，脚本会核查本人 36 条 `none` / `trustgate` 工具说明攻击。

Vanda：先进入 PBS 计算节点，激活 `dsa4213`。以实验四为例：

```bash
python scripts/formal/extract_metadata_trace_checks.py \
  --person 4 \
  --shard-dir /实际路径/原始分片目录 \
  --output results/formal/metadata_diagnosis/trace_checks_person-04.json
```

Mac / WSL：在本人原环境中使用同一脚本，额外加 `--platform local`。以实验二为例：

```bash
python scripts/formal/extract_metadata_trace_checks.py \
  --platform local --person 2 \
  --shard-dir /实际路径/原始分片目录 \
  --output results/formal/metadata_diagnosis/trace_checks_person-02.json
```

其他集群须在该平台分配的计算节点中运行；`--platform local` 只取消 Vanda 的 PBS 检查，不豁免平台调度规则。原始目录结构若不同，应适配路径读取，不修改原件或通过伪造环境变量绕过检查。

| 实验 | 人员参数 | 唯一需要交的文件 |
|---|---|---|
| 2 | `--person 2` | `trace_checks_person-02.json` |
| 3 | `--person 3` | `trace_checks_person-03.json` |
| 4 | `--person 4` | `trace_checks_person-04.json` |
| 5 | `--person 5` | `trace_checks_person-05.json` |

脚本成功后会输出 `passed: true`、`cases: 36` 和 `new_model_requests: 0`。提交对应 JSON 到 `results/formal/metadata_diagnosis/`，在自己的分支开 PR 即可。若报错，保留错误信息和原件，由汇总人定位原因，不要手改检查结果、补造缺失记录或重复调用模型。

该脚本已在实验一的 Vanda 原件上验证。其他平台的实际原件仍需通过相同字段、状态和源码校验；尚未交付的检查不能预先记作完成。
