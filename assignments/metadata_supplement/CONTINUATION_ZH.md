# 运行中断与剩余清单

原评估清单共 144 条。第 128 条（`11df1052bb099ae64ee7`，任务 23、分隔符、调用示例模板、重复 2）在第三次模型请求遇到 60 秒读取超时，原批次按规则停止。该记录保留为接口错误，未重跑或替换，不当作一次有效攻击失败。

[续行清单](continuation-01.json)只包含原顺序中的第 129–144 条，全部此前未启动。记录原结果、原执行摘要、父清单和续行脚本的哈希，防止重复运行或覆盖已有数据。续行预算从原评估 $3 的余量中划出 $1；原超时请求仍保留 $0.05 预留，总停止预算没有扩大。

开发和原评估的执行器 `study.py` 保持冻结。`continue_remaining.py` 复用完全相同的 `FormalExperiment`、模型、工具、阈值、评分和每案例调用上限，只负责明确的剩余案例循环及独立预算账本。它不提供自动重试。

汇总保留 144 个预定 ID，其中 143 个有效比较，1 个接口失败。模型调用预算耗尽属于有效任务失败，仍进入比较；接口超时单列。原始部分评分以状态观察保留，并通过 `valid_for_comparison` 防止将接口错误计作防御成功。无防护/TrustGate 的 18 对配对全部有效。

本次私有记录分为 `evaluation/` 与 `continuation-01/` 两段；重新导出时必须同时传入：

```bash
python scripts/supplement/analyze.py runs/metadata_supplement/development runs/metadata_supplement/evaluation --continuation runs/metadata_supplement/continuation-01
python scripts/supplement/audit_calendar.py runs/metadata_supplement/evaluation --continuation runs/metadata_supplement/continuation-01
```
