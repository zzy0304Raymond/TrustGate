# 第 3 人 Linux / WSL 本机适配

本目录是待审核的独立平台适配器。没有修改 `trustgate/`、`experiments/mvp/` 的 25 个冻结 Python 文件，也没有修改正式清单、权限、攻击、模型、阈值或试验顺序。原 Vanda PBS 入口保持原样。

## 当前验证边界

2026-10-18 已在本机真实 WSL2 / Ubuntu 22.04.5 / Python 3.10.20 完成部署，工作目录为 `/home/trustgate/TrustGate`，环境位于 `/home/trustgate/.local/share/trustgate-env`，不修改 Windows 或 Ubuntu 的系统 Python。WSL 当前约 7.6 GiB 可用内存上限，CPU 推理按原配置使用 2 线程，不使用 GPU。

初次单元测试和运行验证见 `tasks/03/LOCAL_READINESS.json`，后续恢复检查见 `tasks/03/RESUME_REVIEW.json` 和 `tasks/03/PROGRESS.md`。116 条依赖约束逐项匹配，25 个冻结源码和六个模型文件哈希匹配。真实三个 MCP 服务通过 24 个工具描述/schema 核对、全部 60 个攻击传输/目标可达性/权限拒绝检查和 34 条脚本回复循环；固定检测器在 CPU 上完成两条真实推理冒烟检查。测试中的模型回复为脚本，不是 LLM 成绩。Windows 上用简化 fixture 写文件，Linux 测试使用实际原子写入。

2026-10-19 已完成真实开发试跑和正式 336 条采集，记录见 `tasks/03/PILOT_READINESS.json`、`tasks/03/FORMAL_COMPLETION_REVIEW.json`。保留 1 条 TimeoutError。标准交付现位于 `experiments/deliveries/person-03/`；正式费用约 $0.51、含开发试跑约 $0.52，按用户批准的近似口径报告，原记账和预留释放记录见 ACCOUNTING.json。精确已返回正式费用仍为 $0.51220968。已运行的目录不能删除重跑；恢复流程见 `tasks/03/RECOVERY_ZH.md`。Vanda 验收及组员对独立适配器的接收仍未完成，格式兼容不等于自动获得组内批准。

适配器继承原 `FormalExperiment`，只覆盖 MCP `start()`，删除对 PBS 作业变量的依赖；模型请求、工具执行、防护与评估方法均继承原代码。分片调度与预算封装在独立入口实现；未知费用、网络失败、拒绝覆盖和身份检查继续保留。只允许第 3 份、336 次、每人 $2 停止预算；无需 GPU。

原 `test_runner_isolation.py` 的 mock 新增了仅限测试作用域的假作业号，修正该测试在非 PBS 主机上写模拟 manifest 时的 KeyError；没有在本机实际执行环境伪造作业号。

## 本机已经配置完成：Windows 操作入口

在当前 Windows 仓库根目录打开 PowerShell。密钥通过隐藏输入保存到 Linux 私有文件，权限 600，不进入命令参数、Git 或输出：

```powershell
.\scripts\platforms\local\local.ps1 -Action SetKey
.\scripts\platforms\local\local.ps1 -Action Check
.\scripts\platforms\local\local.ps1 -Action CheckKey
```

CheckKey 使用 OpenRouter 官方只读 [GET /api/v1/key](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key)，验证凭据和 key 的额度上限状态，不创建生成请求，不打印密钥、标签或详细余额。key 的额度上限不是账户总余额，也不能证明目标供应商当前可服务。正式 Run 也会在创建试验目录前执行此检查，避免明显无效的密钥占用正式运行编号。

需要重新验证时：

```powershell
.\scripts\platforms\local\local.ps1 -Action Test
.\scripts\platforms\local\local.ps1 -Action Offline
```

确认本份未重复运行、组内接收方式及运行编号后，以下命令才会启动收费 API；正常结束后导出：

```powershell
.\scripts\platforms\local\local.ps1 -Action Run -RunId formal-v1-001
.\scripts\platforms\local\local.ps1 -Action Export -RunId formal-v1-001
```

Run 期间请求 Windows 阻止自动睡眠，结束时恢复；仍需保持供电，避免主动睡眠/关机。Export 自动生成真实 `ENVIRONMENT.md`，并仅把四个公开交付文件复制回 Windows 本分支，不复制原始状态或请求。

改适配代码后可用 `-Action Sync` 同步明确列出的适配文件和测试，不覆盖冻结源码、密钥或运行目录。正式启动后不要 Sync 或修改适配器；改动会改变独立版本哈希。

## 1. 准备真实 Linux 环境

在 Windows 配好 WSL Ubuntu 后，进入 Linux 家目录重新克隆，避免桌面工作副本的 CRLF 和 Windows 路径问题。适配文件需要先保存到一个 Git commit 或复制到 Linux 克隆的相同相对路径；当前 GitHub 分支未自动包含这些未提交的新文件。

```bash
git -c core.autocrlf=false clone --branch experiment-3 \
  https://github.com/zzy0304Raymond/TrustGate.git ~/TrustGate
cd ~/TrustGate
```

创建 Python **3.10.20** 环境，按 `docs/REPRODUCE_ZH.md` 安装原依赖和约束。不要直接用 Ubuntu 默认 Python 或更换 CPU-only Torch 包：冻结版本为 `2.7.1+cu126`，但实际推理在 CPU。本机已通过 conda-forge 的 micromamba 创建独立环境，再用 PyTorch 官方 cu126 源和 PyPI 安装锁定依赖。

在每次启动 Python **之前**设置：

```bash
export PYTHONHASHSEED=0 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TRUSTGATE_DETECTOR_DIR="$PWD/models/prompt_injection_detector"
```

没有设置或伪造 `PBS_JOBID`。本机入口在实际 PBS 作业中会拒绝启动，应使用原入口。

## 2. 模型准备与无 API 验证

```bash
python scripts/platforms/local/prepare_detector.py --detector-dir "$TRUSTGATE_DETECTOR_DIR"
python -m pip check
python -m unittest discover -s tests -v
python scripts/platforms/local/run.py --check --detector-dir "$TRUSTGATE_DETECTOR_DIR"
python scripts/platforms/local/offline.py --detector-dir "$TRUSTGATE_DETECTOR_DIR"
```

模型准备只下载固定 revision 的六个模型文件，并校验原清单中的 SHA，不写原 `models/detector_manifest.json`。`--check` 不读取密钥、不调用 API，校验实际 Linux/Python/依赖/源码/模型。`offline.py` 使用实际 MCP 检查全部 60 个攻击，执行 34 条脚本回复任务循环（循环内检测器为 stub），再运行真实检测器的两条 CPU 冒烟推理；不测真实模型效用、攻击效力或检测器整体准确率。报告保存在 `runs/local-offline/`。

原 `scripts/formal/preflight.py` 仍要求真实 PBS，只在 Vanda 验收时执行；不要伪造 PBS 环境运行它。本机已执行对应 60 个攻击传输范围检查，但仍不能代替 Vanda 上的独立验收。

## 3. 正式执行（有 API 费用）

先由组里审核适配器及离线报告，确认是否接受此平台、清单和本份未重复运行。仓库原有“公共执行器修改后统一验证/换版”的流程仍适用；本目录的格式兼容性不构成组里已批准的例外。

密钥在 Linux 私有文件保存并 `chmod 600`，只传路径；必须是授权 Group 9 密钥。以下 `--execute` 才会调用模型，不要在环境准备阶段运行：

```bash
export TRUSTGATE_KEY_FILE=/你的私有目录/openrouter_group9.key
python scripts/platforms/local/run.py --execute \
  --detector-dir "$TRUSTGATE_DETECTOR_DIR" --run-id formal-v1-001
```

确认统一运行编号后再使用示例编号。结果仍在 `runs/studies/<run-id>/shard-02/`。不支持自动续跑，不删除失败记录重跑。保持电脑供电且不睡眠；不能承诺与集群相同耗时。$2 是客户端停止预算，不是供应商账单保证。

## 4. 导出与审核

必须使用本目录导出器：它调用原 `export_delivery` 生成完全相同的 `results.csv`、`receipt.json`，额外生成真实本机凭据 `platform_receipt.json`。原始凭据中的 `source_sha256` 确实对应未改动的冻结源码；本机适配器是额外执行代码，其独立哈希没有被隐瞒或假写成冻结代码。

字段和指标格式沿用原导出器；导出后只把 CSV/receipt 换行规范为 LF，再计算文件哈希，避免 Git 的 CSV 换行规范使哈希失效。交付与验收在 Linux 上执行，保留 LF。Windows 若启用自动 CRLF 转换，不要从转换后的 JSON 工作副本验收文件字节哈希。

```bash
python scripts/platforms/local/delivery.py export \
  --worker-dir runs/studies/formal-v1-001/shard-02 \
  --destination experiments/deliveries/person-03
```

本机导出器自动生成 `ENVIRONMENT.md`，记录实际平台、CPU/内存、Python/依赖、commit、运行编号、源码/清单/适配器版本和未验证事项。已有人工说明不会覆盖，可继续补充分析。不要提交密钥、原始请求或模拟状态。

审核人根据实际审阅过的适配代码确定哈希白名单文件，格式是 `{相对文件路径: SHA256}`，对应 `platform_receipt.json` 的 `adapter_sha256`。可以计算当前代码哈希作为审核输入，但不能只信任交付者自行声明的值；本工具不是签名或防恶意伪造机制。

```bash
python -c 'import sys,json; sys.path.insert(0,"scripts/platforms/local"); from runtime import adapter_hashes; print(json.dumps(adapter_hashes(),indent=2))'
```

审核后保存为例如 `reviewed-local-adapter.json`，在汇总前运行：

```bash
python scripts/platforms/local/delivery.py audit \
  --deliveries experiments/deliveries \
  --approved-adapter /审核记录/reviewed-local-adapter.json --require-complete
```

校验完整性、分片归属、全部身份字段、关键依赖、预算与行费用、平台凭据和交付文件哈希；发现本机 sidecar 却没有明确批准的适配器哈希时会拒绝。旧 PBS 凭据兼容原四包格式，实际平台仍需人工对照 ENVIRONMENT.md 和私有 manifest；缺少 sidecar 本身不能证明是在 PBS 跑的。工具不能阻止故意删除 sidecar 或伪造数据，必须保留人工验收。

五份收齐且审核通过后，沿用原汇总：

```bash
python scripts/formal/summarize.py --plan assignments/formal/plan.json \
  --deliveries experiments/deliveries --output results/formal/analysis.json
```

本目录没有放宽原汇总器。原汇总器会忽略新增 sidecar，因此新增 audit 必须作为交付验收前置步骤。`--require-complete` 确保五份齐全后才继续最终汇总；仅核查某一份时可省略。person-03 目录增加独立 `.gitattributes` 保持 CSV/JSON 为 LF，避免 Windows Git 换行使凭据哈希失效。最终仍须在 Vanda 计算节点完成共同验收；当前没有该验证结果，也没有自动合并/提交 PR。
