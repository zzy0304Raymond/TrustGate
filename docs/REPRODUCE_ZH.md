# 安装、运行与复现

## 1. 获取代码

```bash
git clone https://github.com/zzy0304Raymond/TrustGate.git
cd TrustGate
```

参考环境是 Python **3.10.20**，Conda 环境名 `dsa4213`。Vanda 上安装、计算和验证均通过 PBS；登录节点仅进行调度、编辑、检查和 Git 操作。CPU 即可，不申请 GPU。

## 2. 安装依赖

已有参考环境可直接使用。新环境在获分配的计算节点中创建，先加载本人的 Conda：

```bash
source /path/to/your/load-conda.sh
conda create -n dsa4213 python=3.10.20 pip
conda activate dsa4213
python -m pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu126
python -m pip install -c requirements-runtime-constraints.txt -r requirements.txt
python -m pip install -c requirements-runtime-constraints.txt -r requirements-analysis.txt
python -m pip check
```

`requirements-runtime-constraints.txt` 固定运行依赖，正式清单还校验六项关键包版本。Torch 为 `2.7.1+cu126`，但推理在 CPU 上执行。旧 `requirements-agentdojo.lock` 和 `requirements-mvp.lock` 是安装历史，不用于覆盖最终约束。分析绘图依赖与运行依赖分开列出。

仅重算公开统计时，Python 3.10.20 标准库即可运行下面的默认入口，不需要 API、模型权重或完整运行依赖。绘图另需 `requirements-analysis.txt`。模型和 MCP 检查使用完整环境。

## 3. 复现公开统计，不调用 API

普通电脑或已分配的计算节点：

```bash
export PYTHONHASHSEED=0
python scripts/reproduce.py --output runs/reproduce
```

Vanda 从仓库根目录提交：

```bash
export TRUSTGATE_CONDA_LOADER=/path/to/your/load-conda.sh
qsub -P personal-YOUR_ACCOUNT -v TRUSTGATE_CONDA_LOADER scripts/reproduce.pbs
```

入口核对五份 CSV、冻结源码、案例完整性、评分分母、诊断及演示来源，并从公开记录重新生成主表和开销表，与已提交表格逐字比较。输出为 `runs/reproduce/`；PBS 入口使用 `runs/reproduce-作业号/`，包含 `run.log`、结果副本及 `verification.json`。它不会读取密钥或重新请求模型。

需要重新画六张图时，加 `--plots`；PBS 使用 `TRUSTGATE_PLOTS=1` 并通过 `qsub -v` 传递。PDF 的生成时间等元数据不作为实验结果，数值表格才是逐字校验对象。

## 4. 准备固定检测器

下载发生在计算节点，只有第一次需要网络：

```bash
python experiments/mvp/prepare_detector.py
export TRUSTGATE_DETECTOR_DIR="$PWD/models/prompt_injection_detector"
```

下载版本由 `models/detector_revision.txt` 指定，正式清单固定六个模型文件的 SHA256。已有缓存可以直接设置其绝对路径。权重不上传 Git。

## 5. 完整离线系统验收

```bash
export TRUSTGATE_CONDA_LOADER=/path/to/your/load-conda.sh
export TRUSTGATE_DETECTOR_DIR=/path/to/frozen/prompt_injection_detector
export TRUSTGATE_FULL_CHECK=1
export TRUSTGATE_PLOTS=1
qsub -P personal-YOUR_ACCOUNT \
  -v TRUSTGATE_CONDA_LOADER,TRUSTGATE_DETECTOR_DIR,TRUSTGATE_FULL_CHECK,TRUSTGATE_PLOTS \
  scripts/reproduce.pbs
```

这一模式额外运行完整回归测试、依赖校验、24 工具适配、60 攻击传输与目标可达性、20 任务权限和七配置检查、合法说明及参考调用误报检查、八组双传输检查、六组真实 MCP 演示。模型回复在这些机制检查中是预设的；不会产生新的 LLM 效果数据。

已经位于 PBS 计算节点时，可直接运行 `python scripts/reproduce.py --full --plots --output runs/reproduce-new`。完整模式的输出目录应使用新名称，避免覆盖先前控制记录。不能伪造 PBS 变量来绕开集群规则。

## 6. 重新运行真实模型实验

提供本人获授权的 OpenRouter 凭据，放在私有文件中并 `chmod 600`，通过 `TRUSTGATE_KEY_FILE` 指定路径。也支持进程环境中的 `OPENROUTER_API_KEY`；不要把密钥值放进命令行、Git 或 PBS 导出参数。

| 研究 | 冻结清单 | 执行入口 |
|---|---|---|
| 原正式 1,680 条 | `assignments/formal/plan.json` | [五份正式运行](FORMAL_START_ZH.md) |
| 工具说明补测 156 条 | `assignments/metadata_supplement/` | [补测运行说明](../scripts/supplement/README_ZH.md) |
| 双传输验证 48 条 | `assignments/transport_validation/plan.json` | `scripts/transport/run.pbs` |

使用全新检出目录与新运行编号，复用发布清单，不重新选任务或模板。核心源码、模型和关键依赖的校验必须通过；保持失败与超时，基础设施错误不自动重试。新采样不能覆盖原 `results/` 中的实测成绩。

双传输启动文件将新统计导出到 `runs/transport_validation/export/`。独立导出也可使用 `python scripts/transport/export_run.py --run runs/transport_validation/live --controls runs/transport_validation/live-controls --output runs/transport-validation-export-new`。

Vanda 启动文件中的项目、Conda 加载器、凭据及模型目录需配置为本人路径。双传输入口传递 `TRUSTGATE_KEY_FILE,TRUSTGATE_DETECTOR_DIR,TRUSTGATE_CONDA_LOADER`；说明补测的既有入口需按本人环境设置 Conda 加载路径。其他调度器使用其实际分配的计算节点，参考 [跨平台要求](CROSS_PLATFORM_CHECKLIST_ZH.md)。

## 7. 演示

下载 `demos/index.html` 并在浏览器打开，或运行 `python scripts/demo/show.py` 查看记录回放。真实 MCP 机制检查已包含在完整验收入口中。见 [演示说明](../demos/README_ZH.md)。
