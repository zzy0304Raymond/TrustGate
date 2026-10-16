# 五份实验共同遵守的接口

## 案例与分片

一个执行案例必须包含 `case_id, workflow, task, surface, condition, repeat, transport`。`surface` 为 `benign/output/metadata`；七种 condition 的名字在 `trustgate/planning.py` 中固定。模型、供应商、提示版本、阈值和预算来自清单 config，不按节点私自改变。

新增正式案例还需 `attack_case_id, attack_task, attack_vector, metadata_tool, payload, template_family, split`。这些扩展在共同准备阶段形成审查清单并统一接入；当前 MVP 仍从 config 读取固定攻击参数。不要把未接入的字段当成已经生效。

每路只拥有自己的 `runs/studies/<run-id>/shard-NN/`，任何分支不能共享修改同一个 state.pickle。模型文件共享只读。

## 权限

权限从原用户请求与攻击前可信资源目录确定，最少包含 `origin, task_prompt, read_tools, writes`。写权限约束工具、对象、收件人和参数；不得读取 `ground_truth`、攻击者目标或隐藏评估结果。共同准备阶段扩展范围时保留现有 `make_policy(task, env, runtime)` 和 `authorize(policy, name, args)` 的调用接口。

## 检测

`Detector.score(text)` 返回 `score, blocked, seconds, windows`。阈值在开发集确定，测试集冻结后不能调整；文档长于一个窗口时必须覆盖全文。来源标注不能在提示中虚构可信度或授予额外权限。

## 输出

每条结果至少包含 `case_id`、案例身份字段、`status, native_utility, attacker_success, safe_completion, injection_reached_model, seconds, api_calls, cost_usd, result_dir`。错误、超时和拒绝保留记录，未到达注入位置不能混同“攻击被阻止”。

统一的汇总统计以全部已计划案例为分母，并另报已执行/已到达子集。按任务分组、配对比较条件；同一攻击三次重复不算三个独立攻击种类。说明攻击和输出攻击分开报告。

## 共同文件修改

五位成员使用同一个冻结版本运行各自数据，不分别开发五个模块。正式运行期间不单独修改模型、权限、检测器、提示或主循环；需要改代码时先统一审核和更新版本，再重新发布清单。

每人只写自己的 `experiments/deliveries/person-NN/` 和对应运行目录。结果汇总与报告使用全部五份，避免各写一套不一致的指标。
