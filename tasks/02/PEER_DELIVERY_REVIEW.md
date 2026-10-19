# 第2人提交前的交付方式与效果核对

核对对象为2026-10-19读取的其他四个实验分支及其PR。只参考交付格式与观测结果，不修改任何组员数据，也不将不同任务分片按成功率排名。

| 人员 | 分支 | 记录 | API已报告费用（美元） | 原生任务通过 | 攻击成功/252 |
|---|---|---:|---:|---:|---:|
| 1 | experiment-1 | 336/336 | 0.71732400 | 219/336 | 12/252 |
| 2 | experiment-2 | 336/336 | 0.72108042 | 168/336 | 5/252 |
| 3 | experiment-3 | 336/336 | 0.51220968 | 232/336 | 0/252 |
| 4 | experiment-4 | 336/336 | 0.45516825 | 305/336 | 1/252 |
| 5 | experiment-5 | 336/336 | 0.66977826 | 223/336 | 24/252 |

上述费用是各CSV的usage.cost行费用之和；第3份另有其负责人批准的近似报告与历史预留调整，应按该份ACCOUNTING/ENVIRONMENT说明理解。不同人员分配不同任务、攻击案例和平台，不能据此推断谁的防护更好或谁运行有误。

## 采用的交付方式

- 固定分支experiment-2，结果目录experiments/deliveries/person-02。
- 主结果results.csv、标准字段receipt.json、实际ENVIRONMENT.md和本人PROGRESS。
- 与本机WSL的第3份类似，本份另保留平台、恢复和费用凭据；Mac的Torch构建差异如实披露。
- 失败、调用上限和权限拒绝记录均保留，不通过重跑改善成绩。
- 第2人只交付一份336条results.csv；暂停前150条与恢复后186条备份仅保留本地。
- PR审阅后才由组员合并main；本次不自动合并。

## 联合结构检查

未修改的scripts/formal/summarize.py在临时目录成功读取五份交付：planned=1680、recorded=1680、complete=true。此结果只验证公开字段、试验身份和覆盖，不表示Mac/Vanda平台等效或全组研究结论已获批准。

## 参考PR与分支快照

- 第1份：[PR #3](https://github.com/zzy0304Raymond/TrustGate/pull/3)，分支快照`2886da358b2898527a01e2d770561df824197439`。
- 第3份：[PR #4](https://github.com/zzy0304Raymond/TrustGate/pull/4)，分支快照`17283dc96590b7de31ebc1a030dcc96383653569`。
- 第4份：[PR #1](https://github.com/zzy0304Raymond/TrustGate/pull/1)，分支快照`9fc1ad2224df673fe335fe1125c7f5136601bb22`。
- 第5份：[PR #2](https://github.com/zzy0304Raymond/TrustGate/pull/2)，分支快照`931dc9435a604026d194a5552abe7b6a86b3c209`。
