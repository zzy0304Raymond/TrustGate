# 正式实验：五人各跑一份

正式数据已配齐：20 个测试任务、60 个攻击案例、7 种配置、每种 3 次重复，共 1,680 次。每人 336 次，包含 84 次正常实验、126 次输出攻击、126 次说明攻击。每份采用同一份冻结代码、模型、权限和案例。

**本页现有脚本和路径以 Vanda 为基准。**五人开跑前都应完成 [跨平台运行与合并检查清单](CROSS_PLATFORM_CHECKLIST_ZH.md)。使用 NSCC 等其他环境时，先适配并验证；最终公共代码须保留 Vanda 的运行方式，结果须在 Vanda 通过同一版本的校验与汇总。

## 在当前 Vanda 环境直接开始

环境、检测模型和 Group 9 密钥文件均已在当前账号下准备好。五人先各领取一个编号，避免两人领同一份。登录节点只提交和查看 PBS 作业；实际运行均在计算节点。

| 人员 | 对应分支 | 直接提交本人的命令 |
|---|---|---|
| 1 | experiment-1 | `qsub /scratch/xinqi.chen/dsa4213/TrustGate_Project/github/launch_formal/person-1.pbs` |
| 2 | experiment-2 | `qsub /scratch/xinqi.chen/dsa4213/TrustGate_Project/github/launch_formal/person-2.pbs` |
| 3 | experiment-3 | `qsub /scratch/xinqi.chen/dsa4213/TrustGate_Project/github/launch_formal/person-3.pbs` |
| 4 | experiment-4 | `qsub /scratch/xinqi.chen/dsa4213/TrustGate_Project/github/launch_formal/person-4.pbs` |
| 5 | experiment-5 | `qsub /scratch/xinqi.chen/dsa4213/TrustGate_Project/github/launch_formal/person-5.pbs` |

以上快捷文件只适用于当前账号、当前共享文件系统。它们不包含密钥值。五份统一使用实验编号 `formal-v1-001`。代码会拒绝覆盖已有结果目录，因此不要在失败后删除目录重新提交。

每个作业申请 2 个 CPU、不申请 GPU，预留 6 小时墙钟上限。历史估计每份约 3 小时 10 分；这不是运行时间承诺，排队和 API 限速会延长等待。`qstat -u "$USER"` 可查看自己的作业。五路作业可能在同一物理主机的不同资源分区运行，不要求五台不同实体机器。

## 其他组员账号或其他克隆目录

以下示例仍使用 Vanda 的 PBS 入口，其中 Conda 加载路径也需要按账号核对。其他平台请先阅读 [平台适配步骤](CROSS_PLATFORM_CHECKLIST_ZH.md#3-换成-nscc-或其他环境时怎么做)；当前执行器要求实际 PBS 作业环境，尚未提供经验证的通用跨调度器入口。

1. 在计算节点克隆自己对应的 `experiment-N` 分支，使用 Python 3.10.20，按 [环境说明](REPRODUCE_ZH.md) 安装锁定依赖。
2. 准备本组授权密钥文件，权限为 600；准备仓库锁定版本的检测器。不要在聊天、提交记录或作业参数中写密钥值。
3. 在自己的仓库根目录提交，所有人约定同一实验编号；以第 1 人为例：

```bash
export TRUSTGATE_RUN_ID=formal-v1-001
export TRUSTGATE_KEY_FILE=/你的私有目录/openrouter_group9.key
export TRUSTGATE_DETECTOR_DIR=/你的模型缓存/prompt_injection_detector
qsub -v TRUSTGATE_RUN_ID,TRUSTGATE_KEY_FILE,TRUSTGATE_DETECTOR_DIR scripts/formal/person-1.pbs
```

第 2–5 人使用对应编号的脚本。也可以由一人提交 `scripts/formal/five_people.pbs` 启动全部五路，但不能同时再提交五份个人作业。

启动前会校验完整清单哈希、源代码、Python、依赖版本、检测模型文件及初始数据状态。校验失败会在调用 API 前停止。正式运行期间不要改模型、参数、权限、攻击或执行代码，也不要重新生成清单。

## 跑完以后

每份私有结果位于 `runs/studies/formal-v1-001/shard-00/` 至 `shard-04/`。编号从 0 开始，对应第 1–5 人。`worker_summary.json` 的 `complete=true` 表示本份全部记录已产生，不表示每个用户任务都成功。

在计算节点导出本份可提交结果。以第 1 人为例：

```bash
python -m trustgate export \
  --plan assignments/formal/plan.json \
  --worker-dir runs/studies/formal-v1-001/shard-00 \
  --destination experiments/deliveries/person-01
```

导出只包含指标和版本凭据；完整对话、邮箱/文件状态和请求日志留在私有目录。每人在自己的实验分支提交 `experiments/deliveries/person-NN/`，完成后再提交 PR，由组员审核合并。

同一交付目录还需补充 `ENVIRONMENT.md`，记录实际运行平台、版本、启动方式和适配情况；字段与最终 Vanda 验收步骤见 [交付检查清单](CROSS_PLATFORM_CHECKLIST_ZH.md#4-每个人需要交付什么)。该说明由本人填写，不由导出工具自动生成。

五份在同一私有目录时，可运行：

```bash
python -m trustgate merge --plan assignments/formal/plan.json --run-root runs/studies/formal-v1-001
python scripts/formal/summarize.py --plan assignments/formal/plan.json \
  --merged runs/studies/formal-v1-001/merged/results.json --output runs/studies/formal-v1-001/analysis.json
```

若五人使用独立账号，收齐五份导出的 `person-NN` 文件夹后，可直接从脱敏交付目录计算指标：

```bash
python scripts/formal/summarize.py --plan assignments/formal/plan.json \
  --deliveries experiments/deliveries --output results/formal/analysis.json
```

汇总包含各配置/攻击面的明确分母、任务完成率、攻击成功率、安全完成率、成本和延迟，以及按任务聚类的配对差异置信区间。重复实验不当作独立任务。正式结论和图表仍需等运行结果产生。

## 中断、失败和费用

每人分配 $2 的 API 停止预算，全组 $10；这是客户端费用控制，不是供应商收费保证。每次请求先预留 $0.05，收到有效 `usage.cost` 后结算。费用未知、网络故障、模型返回成本超出预留或预算不足会停止本份，保留记录。

任务做错、拒绝、权限拦截、模型调用次数耗尽均保留，不为得到成功答案重复。基础设施故障也保留，单独标注，不当作防御成功。当前不自动续跑；出现 `fatal_error` 时先保留整个目录和费用记录，再单独制定有界补跑清单。不要删除记录、重新跑整份或把开发验证结果补进正式测试。
