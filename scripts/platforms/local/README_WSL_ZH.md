# WSL / Linux 运行来源

第 3 份正式实验在 WSL2 / Ubuntu 22.04.5、Python 3.10.20 上完成，共 336 条，其中保留一条 TimeoutError。数据、环境与恢复凭据位于 [person-03](../../../experiments/deliveries/person-03/README.md)，共同统计与误差分母见 [正式结果](../../../results/formal/README_ZH.md)。

本目录继承冻结的 `FormalExperiment`，独立适配 MCP 进程启动及本机调度，不伪造 PBS 作业号。核心源码、模型、权限和攻击清单保持冻结；实际适配器哈希随交付保存。`tasks/03/resume.py`、早期恢复版本和校验脚本保留在原路径，以便核验来源。

## 环境与离线检查

按 [统一复现说明](../../../docs/REPRODUCE_ZH.md) 安装 Python 3.10.20 与固定依赖。Linux/WSL 的正式适配使用 Torch 2.7.1+cu126，并在 CPU 上运行。

```bash
export PYTHONHASHSEED=0 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TRUSTGATE_DETECTOR_DIR="$PWD/models/prompt_injection_detector"
python scripts/platforms/local/prepare_detector.py --detector-dir "$TRUSTGATE_DETECTOR_DIR"
python scripts/platforms/local/run.py --check --detector-dir "$TRUSTGATE_DETECTOR_DIR"
python scripts/platforms/local/offline.py --detector-dir "$TRUSTGATE_DETECTOR_DIR"
```

这些本机入口在真实 PBS 作业中会拒绝运行；Vanda 应使用公共 PBS 入口。离线检查用预设回复，不计入模型效果实验。

## 复现本份真实模型实验

本机入口只负责原第 3 份；使用新检出目录、新运行编号和私有凭据文件，保留发布数据。

```bash
export TRUSTGATE_KEY_FILE=/absolute/private/openrouter_group9.key
python scripts/platforms/local/run.py --execute \
  --detector-dir "$TRUSTGATE_DETECTOR_DIR" --run-id replication-person3-001
python scripts/platforms/local/delivery.py export \
  --worker-dir runs/studies/replication-person3-001/shard-02 \
  --destination runs/export-person03
```

记录保留拒绝、超时及调用上限。导出包含相同指标和本机来源凭据；不公开密钥、请求及模拟状态。原结果的跨平台统计在统一入口验证，但本机运行速度不能直接解释为与 Vanda 的硬件比较。
