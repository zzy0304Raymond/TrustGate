# 重新运行冻结正式实验

发布数据已完成，共 1,680 条。以下命令用于从固定设计产生一次新的模型采样；只想复现统计和演示时，使用 [无 API 复现入口](REPRODUCE_ZH.md)。

## 设计和环境

`assignments/formal/plan.json` 固定 20 个任务、60 个攻击、7 种配置和三次重复。五个分片各 336 条：84 正常、126 输出攻击、126 说明攻击。每份均含全部配置。任务分配见 [分片表](TEAM_PLAN_ZH.md)。

在新克隆的 `main` 中，按 [安装说明](REPRODUCE_ZH.md) 准备 Python 3.10.20、固定依赖和检测器。运行前会验证核心源码、依赖、权重、案例和初始状态。不要重新生成清单来绕过不一致。

## Vanda PBS 启动

在仓库根目录设置路径和一个新的运行编号。凭据文件必须属于本人、权限为 600；参数中只传路径。

```bash
export TRUSTGATE_RUN_ID=replication-001
export TRUSTGATE_CONDA_LOADER=/path/to/your/load-conda.sh
export TRUSTGATE_KEY_FILE=/absolute/private/openrouter_group9.key
export TRUSTGATE_DETECTOR_DIR=/absolute/models/prompt_injection_detector
qsub -P personal-YOUR_ACCOUNT \
  -v TRUSTGATE_RUN_ID,TRUSTGATE_CONDA_LOADER,TRUSTGATE_KEY_FILE,TRUSTGATE_DETECTOR_DIR \
  scripts/formal/five_people.pbs
```

数组作业申请五个独立 CPU 分片，各 2 CPU、8 GB、最多六小时，不申请 GPU。实际并发和排队取决于调度器。每份停止预算为 2 美元，共 10 美元；这是原冻结客户端预算，运行时间不是承诺。

也可以分别提交 `scripts/formal/person-1.pbs` 至 `person-5.pbs`，使用相同变量和新的运行编号。数组方式和个人方式选择一种，避免重复。

## 结果与汇总

每份输出在 `runs/studies/replication-001/shard-00/` 至 `shard-04/`。目录已存在时拒绝覆盖。拒绝、任务失败、调用上限和基础设施错误均保留；基础设施故障不会自动重新请求模型。

五份结束后，在计算节点汇总：

```bash
python -m trustgate merge \
  --plan assignments/formal/plan.json \
  --run-root runs/studies/replication-001
python scripts/formal/summarize.py \
  --plan assignments/formal/plan.json \
  --merged runs/studies/replication-001/merged/results.json \
  --output runs/studies/replication-001/analysis.json
```

未齐全时可用 merge 的 `--allow-partial` 检查状态，结果会标示不完整。`complete` 只代表记录覆盖，不代表所有用户任务成功。

脱敏导出示例：

```bash
python -m trustgate export \
  --plan assignments/formal/plan.json \
  --worker-dir runs/studies/replication-001/shard-00 \
  --destination runs/export/person-01
```

新结果保持独立，不替换发布的 `experiments/deliveries/` 或 `results/`。原始请求、完整模拟状态和凭据保留私下。原正式数据可直接由统一复现入口重算，详细平台与计时口径见 [开销分析](../results/formal/overhead/README_ZH.md)。

其他平台先按 [兼容要求](CROSS_PLATFORM_CHECKLIST_ZH.md) 配置实际运行入口。本项目的统一系统验收环境为 Vanda；不能伪造 PBS 作业环境。
