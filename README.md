# TrustGate

研究问题：模型读取不可信的工具说明或工具返回文字时，能否通过来源标注、说明筛查和执行授权，阻止越权操作，同时完成用户任务？

本仓库提供已经运行过的 AgentDojo + MCP 实验基础、七种对照配置、六类业务、五路任务拆分、费用控制、结果汇总和可复现检查。邮件、日历和文件均是模拟对象。

**当前状态：**历史试验共 102 次，293 次 API 调用，响应报告成本约 $0.132；这些是开发结果，不是正式测试结论。日程写入仍不稳定，工具说明攻击尚未在无防护下成功。正式 20 个任务、60 个攻击案例和相应权限规则仍需共同完成审查与冻结。五人分工现按正式实验分片，每人 336 次，预计约 3.2 小时机器运行。`main` 是共同的可运行基础，不能把待完成研究标成已完成。

## 从哪里开始

1. 阅读 [五人分工与合并顺序](docs/TEAM_PLAN_ZH.md)，每位成员选择 experiment-1 至 experiment-5 中的一个实验分支。
2. 按 [运行说明](docs/REPRODUCE_ZH.md) 在 PBS 计算节点检查环境并运行离线测试。
3. 阅读本分支 `tasks/0N/ASSIGNMENT.md`，按验收清单运行自己的 336 次实验并交付结果。
4. 完成后发起 PR。五个任务分支尚未合并，组员自行审核后合并。

## 共同基础包含什么

| 目录 | 内容 |
|---|---|
| `experiments/mvp/` | 真实 MCP 服务、原生模拟状态、检测器、六类业务、七种配置、原生评估和历史复测程序 |
| `trustgate/` | MVP 执行、费用与汇总；正式实验的五人工作量分配 |
| `assignments/formal/` | 1,680 次正式实验分配，每人 336 次；尚未冻结为可执行清单 |
| `configs/mvp/` | 已验证的 MVP 参数和正式研究数量计划 |
| `scripts/` | PBS 五路数组作业、离线检查入口 |
| `tests/` | 清单完整性、费用、权限、结果合并的回归检查 |
| `results/pilot/` | 102 次历史试验的汇总数据；原始状态和 API 明细保存在私有计算目录 |
| `docs/` | 运行、接口、分工、实测结果和研究局限 |

## 正式实验五人分片

五份分别约 3 小时 9 分、3 小时 9 分、3 小时 10 分、3 小时 11 分、3 小时 11 分。每份都含全部七种配置；大家运行不同案例，不再各自开发一个模块。详见 [当前分工](docs/TEAM_PLAN_ZH.md)。

重新生成工作量清单：`python scripts/allocate_formal.py`。该操作不调用 API，清单明确标记正式实验尚未就绪。

## 当前可运行的 MVP 五路工具

在计算节点、仓库根目录运行：

```bash
export PYTHONHASHSEED=0 TOKENIZERS_PARALLELISM=false
python -m trustgate plan --workers 5 --budget-usd 1 --output runs/plans/pilot-five.json
python -m trustgate inspect --plan runs/plans/pilot-five.json
```

以上只准备清单，不调用 API。当前执行器支持固定的 81 次 MVP；正式 1,680 次必须先完成案例与权限冻结，再统一接入同一执行协议。

提交方法、密钥配置、模型缓存与结果合并见 [运行说明](docs/REPRODUCE_ZH.md)。五个作业会分别获取计算资源；调度器可能把它们放在同一物理主机。需要五台不同主机时另行申请明确的节点布局，不能把“五个作业”直接当成“五台物理机器”。

## 研究纪律

- 使用统一模型、供应商、提示和预算；改变版本后单独记录，不混合不同版本的成绩。
- 隐藏评估答案只用于隔离的适配器检查和最终评估，不用于制定权限或提示。
- 所有失败均保留；不能重复执行直到成功后只报告成功。
- 报告 API 返回的 `usage.cost`，与账户账单余额分开。费用预留是客户端保护，不是供应商保证的收费上限。
- 不提交 API 密钥、全组密钥 CSV、下载的模型权重、原始邮箱/文件状态或包含完整请求的日志。

技术来源：[AgentDojo](https://github.com/ethz-spylab/agentdojo)、[MCP](https://modelcontextprotocol.io/specification/2025-03-26/server/tools)、[固定版本检测器](https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2)。各依赖和基准数据沿用其上游许可证，本仓库未代替成员决定新增项目许可证。
