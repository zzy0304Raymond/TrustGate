# 第 3 人本机适配与实验来源

本份数据使用 WSL2 执行。公共代码、平台适配逻辑和结果格式已在 Vanda PBS 计算节点完成离线检查；最终数据清单及实验限制见 [正式结果说明](../../results/formal/README_ZH.md)。

## 当前状态与结果入口

2026-10-19 已完成正式 336 条采集。标准交付位于 `experiments/deliveries/person-03/`，包括原格式 `results.csv`、`receipt.json`、实际 `ENVIRONMENT.md`、平台/恢复来源和分析。此前 `tasks/03/delivery_pending/` 是保留的历史审核快照，已经由标准交付替代。

正式实验已返回 API 费用为 $0.51220968，含开发试跑约 $0.52。一次超时请求的最终供应商收费未知；`ACCOUNTING.json` 保留原执行记账及客户端预留释放记录。

336 条包括 1 条 TimeoutError 和 12 条 model_call_budget；未重跑、替换或删除失败。各案例耗时之和 6,750.43 秒，不包含启动、导出或用户暂停，不能与其他组员的完整 worker 墙钟时间直接混同。完整覆盖不表示模型全部答对，本份无防护攻击也未成功，不能据此断言额外防护有效。

## 改动边界

- 保留正式 plan SHA `b1817378e174e1cd742acedc465e63620a1dbe3bdbdca92c86c70d26d01f42c6`；25 个冻结执行文件按 Linux 原始字节验证通过。
- 不改变任务、攻击、分片、顺序、权限、模型/供应商、提示、阈值、预算或三次重复。
- 新增 `scripts/platforms/local/` 独立平台代码；`FormalExperiment` 只覆盖 MCP 启动方式，不覆盖模型请求、实验循环、权限或评估方法。
- 独立分片调度器继承原预算对象和冻结实验类，仅运行 person-03；额外记录完整适配器哈希、真实平台、包版本与模型哈希，没有冒充 PBS 作业。
- 原 PBS 脚本和公共源码未变。原隔离测试仅补了 mock 范围内缺失的作业号，允许非 PBS 主机运行该单元测试。
- person-03 下的 `.gitattributes` 保证公开 CSV/JSON 为 LF；原始模型/状态/请求/密钥不提交。
- `tasks/03/resume.py` 是额外的有界恢复执行代码，单独绑定哈希；各次执行代码快照和失败保留，旧版公共参考为 `resume_v1_20261019.py`。

## 已有证据

见 `LOCAL_READINESS.json`：真实 WSL2 / Python 3.10.20、116 条依赖约束匹配、完整单元测试通过、真实 MCP 的 24 个工具核对、60 个攻击传输/目标可达性/宿主拒绝检查、20 个任务和 14 个配置×攻击面脚本循环、真实固定检测器 CPU 冒烟检查。单元测试包括新增的只读密钥检查（mock，不使用真实凭据）。

本机导出的 336 条模拟记录与另外四份模拟记录，已通过未修改的原汇总器得到 1,680 条完整覆盖。这仅证明格式兼容，不能作为正式 LLM 成绩。

## 复现数据检查

运行 `python tasks/03/audit_delivery.py --accept-estimated-costs` 核对本份数据身份、适配器文件哈希、记账与恢复来源。五份结果统一使用原 `scripts/formal/summarize.py` 与冻结计划汇总，共 1,680 条唯一记录。

`LOCAL_READINESS.json` 保留运行前的离线检查；正式结果位于 `experiments/deliveries/person-03/`，完整汇总位于 `results/formal/`。
