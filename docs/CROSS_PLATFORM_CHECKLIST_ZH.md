# 五人跨平台运行与合并检查清单

**本项目的前期配置和已完成验证以 Vanda 为基准，最终也以 Vanda 作为代码与结果的共同验收环境。**五个人可以使用不同的计算环境，但交付的公共代码必须保留 Vanda 的运行方式，结果必须能够由 Vanda 上的同一套校验与汇总程序读取。当前仓库尚未完成 NSCC 等其他平台的运行验证；不能直接把 Vanda 的路径和作业脚本照搬过去。

这里的“与 Vanda 适配”包括两件事：代码能够在 Vanda 的 PBS 计算节点通过检查并运行；其他平台产生的结果保留真实来源，按统一格式交付并通过版本、任务身份和完整性核对。**不需要把其他平台的结果改写成“在 Vanda 上运行”，也不要求五台机器产生逐字相同的模型回复。**

## 1. 五人先确认自己的那一份

| 人员 | Git 分支 | 分片目录 | 交付目录 | 正式任务编号 |
|---|---|---|---|---|
| 1 | `experiment-1` | `shard-00` | `person-01` | 0、12、17、31 |
| 2 | `experiment-2` | `shard-01` | `person-02` | 2、7、22、32 |
| 3 | `experiment-3` | `shard-02` | `person-03` | 16、24、27、35 |
| 4 | `experiment-4` | `shard-03` | `person-04` | 3、8、18、28 |
| 5 | `experiment-5` | `shard-04` | `person-05` | 5、9、30、33 |

每人 336 次：84 次正常实验、126 次工具输出攻击、126 次工具说明攻击。每份都有全部七种配置、三次重复。五份合计 1,680 次；不要重复领取，也不要为了凑数量加入开发集或历史 MVP 结果。

## 2. 每个人开跑前都要勾选

- [ ] **同一份正式清单。**使用仓库的 [plan.json](../assignments/formal/plan.json) 和对应的 `person-NN.json`，不自行重新生成任务、攻击、权限或试验顺序。当前 `plan_sha256` 为 `b1817378e174e1cd742acedc465e63620a1dbe3bdbdca92c86c70d26d01f42c6`；将来若统一换版，以新发布的清单为准。
- [ ] **同一份实验代码。**冻结清单中的 `source_sha256` 必须与本地代码一致。各分支可以有不同的文档提交和结果提交，因此不要求五个分支的 Git commit 完全相同；应记录各自实际 commit，并确保冻结的运行代码相同。
- [ ] **同一 Python 与依赖。**Python 为 `3.10.20`，按 [环境说明](REPRODUCE_ZH.md) 和 [依赖约束](../requirements-runtime-constraints.txt) 安装；关键包版本须与清单中的 `packages` 一致。当前 Torch 构建为 `2.7.1+cu126`，不要自行换成另一个构建或升级依赖。
- [ ] **同一基准与数据。**使用 AgentDojo `v1.2.2` 的 Workspace 套件，以及已冻结的 20 个任务、60 个攻击案例和权限；每次试验使用程序建立的独立初始状态，不复制别人运行后的邮箱、日历或文件状态。
- [ ] **同一 API 模型与供应商。**模型为 `qwen/qwen3-30b-a3b-instruct-2507`，供应商为 `SiliconFlow`，`temperature=0`。不能自行换模型或改用本地 GPU 模型。使用本组授权密钥，密钥不进入 Git。
- [ ] **同一检测器。**使用 `protectai/deberta-v3-base-prompt-injection-v2`，模型文件哈希与清单中的 `detector_sha256` 一致，阈值 `0.5`，保持当前 CPU 推理方式。
- [ ] **同一试验限制。**每个试验最多 8 次模型调用、每次最多 1,024 个输出 token、任务时间限制 180 秒、拒绝次数限制 3；每种配置重复 3 次。参数见 [正式配置](../configs/formal/frozen.json)，执行以清单内的配置为准。
- [ ] **同一七种配置。**`none`、`delimiters`、`classifier`、`trustgate`、`no_provenance`、`no_metadata`、`no_authorization` 全部保留，不只挑表现好的配置。
- [ ] **同一启动约定。**在启动 Python 前设置 `PYTHONHASHSEED=0`、`TOKENIZERS_PARALLELISM=false`；保持现有脚本的 `OMP_NUM_THREADS=2`、`MKL_NUM_THREADS=2`。当前五人统一实验编号为 `formal-v1-001`，各自只运行本人的分片。
- [ ] **同一费用与失败处理。**每人 API 停止预算 $2，全组 $10，每次请求预留 $0.05；这是客户端控制，不是账单保证。保留失败、超时、拒绝和基础设施错误；不删除已有目录重跑，也不反复重试直到成功。
- [ ] **检查完成再正式运行。**在获分配的计算节点按 [环境说明](REPRODUCE_ZH.md) 完成无 API 检查，包括 `python scripts/formal/preflight.py`，再按 [启动说明](FORMAL_START_ZH.md) 提交本人作业。启动时的清单、代码、依赖、模型文件或初始状态检查报错，应先解决原因。

`python -m trustgate inspect --plan assignments/formal/plan.json` 可以检查清单并显示其 SHA 和分片数量；它不能代替完整的运行环境检查。正式执行器会在调用 API 前检查冻结代码、关键依赖和检测器文件。

## 3. 换成 NSCC 或其他环境时怎么做

**可以不同的项目：**集群名称、账号、仓库绝对路径、Conda 所在路径、模型缓存路径、私有密钥文件路径、作业队列，以及满足资源需求的计算节点型号。环境路径不同本身不会导致结果无法合并。

**当前执行方式：**大模型通过远程 API 调用，本地检测器在 CPU 上运行；仓库的个人作业默认申请 2 个 CPU、8 GB 内存和 6 小时墙钟时间，不申请 GPU。换用带 GPU 的机器不会自动让当前实验使用 GPU，也不应因此改变模型或检测器的执行方式。

按下面的顺序处理平台差异：

1. **先确认平台使用的调度器和可安装的版本。**当前执行器要求实际 PBS 作业环境中的 `PBS_JOBID`。如果目标环境使用其他调度器，现有代码不能直接运行；不要伪造该变量或删除检查。
2. **只需调整路径或作业资源时，单独提供平台启动脚本。**建议放在 `scripts/platforms/<平台名>/`，明确环境激活、路径变量和提交方法；保留 `scripts/formal/` 下的 Vanda 入口。公共 Python 代码、清单、数据和结果格式保持不变。该目录是适配代码的建议位置，不表示仓库已经提供 NSCC 适配器。
3. **如果必须修改执行器、依赖版本或模型执行方式，先统一修改公共版本。**说明变更，保留 Vanda 的运行路径，在 Vanda 与目标平台完成离线验证，再发布新的冻结清单并同步给五个人。需要 API 验证时只使用明确数量和预算的开发验证，结果与正式测试分开。不要五个人各自改代码后直接开始正式实验。
4. **换版后先决定哪些试验受影响。**旧记录原样保留并与新版本分开；补跑使用明确范围、预算和新的运行编号。不能通过修改 `receipt.json`、清单 SHA 或源代码 SHA 来让不一致的结果通过合并。
5. **交付前回到 Vanda 验收。**平台专用启动脚本可以保留，但共享代码必须仍可由 Vanda 的 PBS 入口运行，导出的结果须由 Vanda 上的共同版本成功读取和汇总。

不同平台的 CPU 性能、网络和 API 排队会影响耗时。报告中保留实际平台与运行时间；分析跨平台延迟时说明这些差异，不把原始速度差异直接归因于防护方法。

## 4. 每个人需要交付什么

- [ ] 私有运行目录完整保留，包括实际运行配置、`manifest.json`、`worker_summary.json`、费用记录和故障记录。完整对话、原始请求和模拟状态不提交 Git。
- [ ] 本人 336 个唯一试验 ID 无重无漏；`worker_summary.json` 中 `complete=true` 且 `fatal_error=null`。这表示记录完整，不表示 336 个任务都做对。
- [ ] 使用仓库导出工具生成 `experiments/deliveries/person-NN/results.csv` 和 `receipt.json`，不手工修改列名、试验身份、版本字段或成绩。具体命令见 [启动说明](FORMAL_START_ZH.md)。
- [ ] 在同一交付目录补充 `ENVIRONMENT.md`，写明实际集群、操作系统、CPU/GPU 与实际使用情况、调度器、Python/关键依赖版本、Git commit、清单 SHA、运行编号、分片编号、启动脚本与无密钥的启动方式、平台改动和检查结果。路径包含账号时可脱敏；不要放密钥或访问令牌。
- [ ] 若有平台适配代码，一并提交脚本及说明，注明 Vanda 验证方式与结果；尚未验证的事项如实标注。
- [ ] 只向自己的 `experiment-N` 分支提交本人的结果与说明，更新任务进度并发起 PR。五份完成后由组员审核合并，避免覆盖其他人的交付目录。

`ENVIRONMENT.md` 是人工填写的环境说明，不会由现有导出工具自动生成，也不替代自动生成的 `receipt.json`。

## 5. 最终在 Vanda 上如何验收

由负责汇总的人收齐五份交付，在 **Vanda 已分配的 PBS 计算节点**中操作：

1. 使用共同发布的代码与正式清单，激活 Python 3.10.20 的 `dsa4213` 环境。若包含平台适配或公共代码变更，按 [环境说明](REPRODUCE_ZH.md) 完成离线检查，确认 Vanda 的 PBS 运行入口仍有效；需要开发验证时另设有界清单与预算。
2. 核对五份 `ENVIRONMENT.md` 和导出凭据：人员与分片一一对应，清单与源代码版本一致，每份 `recorded=336`、`complete=true`，并确认各自的导出是在无致命错误的完整运行上生成的。汇总脚本不能代替这些环境与完成状态的核对。
3. 将五个 `person-NN` 文件夹放到 `experiments/deliveries/` 后，在仓库根目录运行：

```bash
source /scratch/xinqi.chen/load-conda.sh
conda activate dsa4213
export PYTHONHASHSEED=0 TOKENIZERS_PARALLELISM=false
python -m trustgate inspect --plan assignments/formal/plan.json
python scripts/formal/summarize.py \
  --plan assignments/formal/plan.json \
  --deliveries experiments/deliveries \
  --output results/formal/analysis.json
```

4. 核对输出为 `planned=1680`、`recorded=1680`、`complete=true`。程序会检查交付的清单与源代码凭据，以及重复、外来或身份不一致的试验记录；记录不齐时不能将汇总当作完整正式结论。
5. 保留各平台来源、费用凭据、错误记录和最终汇总。五份实验分支经过组员审核后再合并到 `main`。

验收通过表示代码运行方式与结果格式符合共同要求，不保证不同硬件/API 时段得到完全相同的答案，也不等于模型任务成功率达标。当前正式实验结果仍需五人实际运行后产生。
