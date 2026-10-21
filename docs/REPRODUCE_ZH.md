# 环境、验证与执行

## 已完成结果与演示的复现入口

无需重新运行模型实验即可查看 [三个演示案例](../demos/README_ZH.md) 和 [机制分析](../results/formal/mechanism_evidence/README_ZH.md)。在仓库根目录提交 `qsub scripts/formal/mechanisms.pbs` 可复现正式统计与证据表。演示的 PBS 命令及检测器路径设置见演示说明；其模型回复是预设的，只验证真实 MCP、检测器与授权逻辑，不产生新的模型实验结果。

## 环境

Vanda 上计算、安装和运行验证在 PBS 分配的计算节点执行；登录节点可用于调度命令、轻量检查、编辑与 Git 操作。环境为 `dsa4213`，Python 必须为 `3.10.20`。不需要 GPU。

```bash
source /scratch/xinqi.chen/load-conda.sh
conda activate dsa4213
python --version
```

既有共享环境已安装依赖。在另一台机器重建时，先创建 Python 3.10.20 环境，再在计算节点执行：

```bash
python -m pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu126
python -m pip install -c requirements-runtime-constraints.txt -r requirements.txt
python -m pip check
```

`requirements-runtime-constraints.txt` 记录当前实际安装版本。当前共享环境的 Torch 是 2.7.1+cu126，实验只在 CPU 上执行；重建命令保留相同构建，不表示需要申请 GPU。构建来源见 [PyTorch 官方历史版本](https://pytorch.org/get-started/previous-versions/)。原 `requirements-agentdojo.lock`、`requirements-mvp.lock` 保留安装历史；不要单独重装前者覆盖最终版本。某些 wheel 与平台有关，若换系统应重新验证并记录环境。

## 密钥与模型

仅使用本小组授权的 Group 9 密钥。可通过已导出的 `OPENROUTER_API_KEY`，或权限为 600 的密钥文件提供；文件路径用 `TRUSTGATE_KEY_FILE` 指定。不要把密钥值放进命令参数、作业名称、Git 或聊天。

首次使用完整防护时，运行 `python experiments/mvp/prepare_detector.py`，按仓库中的 revision 下载模型。多个作业共享读取模型缓存；不要并行下载到同一目录。也可用 `TRUSTGATE_DETECTOR_DIR` 指向已经准备好的同版本缓存。

## 无 API 的检查

```bash
export PYTHONHASHSEED=0 TOKENIZERS_PARALLELISM=false
mkdir -p runs/mvp
python -m unittest discover -s tests -v
python experiments/mvp/preflight.py
python experiments/mvp/test_parser_recovery.py
python -m pip check
```

确定性回放检查 24 个工具、六类业务和攻击传输一致性。测试中的原生 ground truth 仅用于适配器回放，不进入真实模型提示或权限规则。

## 正式实验

执行清单为 `assignments/formal/plan.json`，五人各 336 次、共 1,680 次，已冻结。每人可直接运行对应的 PBS 脚本；完整步骤、当前集群快捷命令和交付方式见 [五人启动说明](FORMAL_START_ZH.md)。

新增无 API 检查：`python scripts/formal/preflight.py`。它检查全部 60 个攻击的 MCP 注入范围与目标可达性，以及 20 个任务、七配置×两入口的真实工具流程。此检查使用脚本模拟模型回复，不能作为 LLM 的任务成功率或攻击成功率证据。

数据生成脚本 `scripts/formal/prepare.py` 仅用于维护冻结版本；组员正式运行时不要重新生成或改动清单。先前的 `allocation.json` 保留作时间估算历史。

## MVP 五路运行

先生成一次清单并检查。清单 SHA 保证五路使用同一实验设计；每个案例有独立 ID，不重复分配。对同一任务/攻击入口/重复编号的不同防护配置尽量放在同一份，按预计耗时平衡五份。

```bash
python -m trustgate plan --workers 5 --budget-usd 1 --output runs/plans/pilot-five.json
python -m trustgate inspect --plan runs/plans/pilot-five.json
```

从仓库根目录向 PBS 提交。下面变量仅为路径和实验编号，不含密钥：

```bash
export TRUSTGATE_PLAN="$PWD/runs/plans/pilot-five.json"
export TRUSTGATE_RUN_ID="pilot-five-001"
qsub -v TRUSTGATE_PLAN,TRUSTGATE_RUN_ID scripts/run_five_workers.pbs
```

默认密钥位于仓库 `.secrets/openrouter_group9.key`。如果使用自定义文件或模型路径，另外通过 `qsub -v` 传递对应路径变量。不要通过 qsub 导出密钥值。

`auto` 路由到普通 CPU 批处理队列。核对时每用户上限为 6 个同时运行的作业；资源或其他作业会减少实际并发。`auto_free` 下多核作业上限不同，不能直接照搬五并发。

每路有独立模拟状态、日志、结果和费用份额。五份份额之和等于总预算，每个请求先预留 $0.05；未知费用、超额或网络错误会停止该路，避免自动重复收费。预留额不是价格保证；若响应费用超过预留额，记录已发生费用并停止。预算较小时，可能因为不足下一次预留而提前结束。

本版本故意拒绝覆盖已有分片目录；没有自动断点续跑。网络失败后先核对记录，另行准备明确的补跑清单并保留费用和原失败记录，不要直接删除目录重跑。

## 合并结果

```bash
python -m trustgate merge --plan runs/plans/pilot-five.json --run-root runs/studies/pilot-five-001
```

只有全部结果、清单身份和每路完成标记都一致才生成“完整”汇总。过程中查看用 `--allow-partial`，输出明确标为不完整。任务失败仍计入已记录实验，不能用“任务成功”替代“实验完成”。

历史 102 次在 `results/pilot/` 中，后续新运行保持独立。更改代码后保存新 commit SHA 和新 run ID。
