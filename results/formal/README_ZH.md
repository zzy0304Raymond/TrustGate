# 正式实验汇总

`analysis.json` 由 `scripts/formal/summarize.py` 读取五份脱敏数据生成，共 1,680 条记录，覆盖 20 个任务、七种配置和三次重复。历史 MVP、开发验证和离线脚本回复单独统计。

原始公开测量位于 `experiments/deliveries/person-01/` 至 `person-05/`。[数据清单](manifest.json) 记录每份数据的文件哈希、运行平台、样本数及 API 返回费用。

## 数据范围与实验局限

- 保留一条 `TimeoutError` 和所有拒绝、调用上限及任务失败。超时不能当作防御成功。
- 第 1、4、5 份在 Vanda；第 2 份在 Mac；第 3 份在 WSL。Mac 使用原生 CPU Torch 2.7.1，其余使用 2.7.1+cu126；模型权重与冻结核心算法相同。不同硬件的数值与延迟可能存在差异，运行时间分析需按平台分层。
- 第 2 份第 151 条通过缓存回复恢复，部分历史 API 耗时来自文件时间；延迟分析应同时报告排除此条的敏感性结果。
- 第 3 份的 `wall_seconds` 是案例耗时之和，不是连续 worker 墙钟时间。
- API 已返回费用合计 **$3.07556061**；第 3 份有一笔超时请求未获得供应商费用响应，其最终收费未知。原 $0.05 为客户端预留，预留释放不代表供应商账单已完成对账。
- `complete=true` 表示记录数量完整。任务成功率、攻击成功率和安全完成率分别报告；运行错误保留在计划样本分母中，有效记录口径另列。结果按任务、配置及攻击面解释。

## 复现汇总

在 Vanda PBS 计算节点、仓库根目录运行以下命令。数据校验与汇总不调用模型 API：

```bash
python scripts/validation/check_deliveries.py
python tasks/02/prepare_delivery.py --check --require-validated
python scripts/formal/summarize.py --plan assignments/formal/plan.json \
  --deliveries experiments/deliveries --output runs/validation/analysis.json
```

[52 条重点记录核查](review/README_ZH.md)提供逐条原因分类、实际防护机制及评分局限。该定向抽查不替代全量正式统计。
