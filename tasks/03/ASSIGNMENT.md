# 第 3 人：正式实验分片

对应分支：`experiment-3`。任务与数据已经配齐，使用共同冻结版本运行本份 **336 次**，不需要自行编写攻击、权限或算法。

- 84 次正常实验、126 次工具输出攻击、126 次工具说明攻击。
- 7 种防护配置，每种 3 次重复；自己的任务清单见 [person-03.json](../../assignments/formal/person-03.json)。
- 预计约 3.16 小时机器运行，另计排队、排错、结果分析与报告。
- API 停止预算 $2；不自动重试模型失败，也不覆盖已有结果。

## 操作

1. 按 [启动说明](../../docs/FORMAL_START_ZH.md) 准备路径或使用当前 Vanda 的快捷脚本。
2. 只提交 `scripts/formal/person-3.pbs`，确保没有别人重复领取此份。
3. 保留运行目录 `runs/studies/formal-v1-001/shard-02/`。任务答错、拒绝或未触发注入都按原样保留。
4. 完成后在计算节点运行：

```bash
python -m trustgate export --plan assignments/formal/plan.json --worker-dir runs/studies/formal-v1-001/shard-02 --destination experiments/deliveries/person-03
```

5. 在本分支提交导出的 `results.csv` 和 `receipt.json`，更新 PROGRESS.md，之后提交 PR 供组员审核。不要提交密钥、原始对话或邮箱/文件状态。

验收：336 个唯一试验 ID 全部记录，plan SHA 与公共清单一致，worker_summary.json 的 complete=true 且无 fatal_error。模型任务成功率另算，不作为删除失败结果的理由。

冻结清单 SHA：`b1817378e174e1cd742acedc465e63620a1dbe3bdbdca92c86c70d26d01f42c6`。
