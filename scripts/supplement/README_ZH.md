# 补测入口

设计和结果见 [冻结协议](../../assignments/metadata_supplement/PROTOCOL_ZH.md) 与 [结果说明](../../results/metadata_supplement/README_ZH.md)。冻结执行器 `study.py` 不应编辑；改动会触发清单校验失败。分析与事后事实核查独立于该执行器。

## 验证已交付结果

在 Vanda PBS 计算节点激活 `dsa4213`（Python 3.10.20），从仓库根目录执行：

```bash
python scripts/supplement/verify_public.py
python -m unittest tests.test_metadata_supplement tests.test_metadata_diagnosis
```

上述操作不调用 API，也不需要原始请求或密钥。

## 重新执行冻结试验

原始执行使用 Vanda、AgentDojo 0.1.35 和既有固定依赖。运行前需有冻结检测器权重，以及本人有权使用的模型服务凭据。请沿用仓库的环境准备说明；不同集群仅适配作业入口，不能自行改模型、工具、阈值、依赖版本、清单或评分。

推荐在全新的检出目录中运行，保留发布的两个 JSON 清单，不重新筛选模板：

```bash
mkdir -p runs
# 将这两个路径替换为自己的私有凭据文件和已准备的检测器目录。
export TRUSTGATE_KEY_FILE=/absolute/private/openrouter_group9.key
export TRUSTGATE_DETECTOR_DIR=/absolute/models/prompt_injection_detector
qsub -v TRUSTGATE_KEY_FILE,TRUSTGATE_DETECTOR_DIR scripts/supplement/run_vanda.pbs
```

`run_vanda.pbs` 按 `PBS_O_WORKDIR` 进入仓库，项目账号和资源需适配本人 Vanda 账户。它只在没有清单时生成新阶段；发布清单存在时原样复用。私有输出目录存在时拒绝运行，以免覆盖或重复消费。

实际复现输出应单独保存，不能替换已经交付的实测结果；模型服务即便温度为 0 也可能产生不同回答。对新结果做离线导出时注意使用独立检出目录，因为导出器会写入该检出的 `results/metadata_supplement/`。新结果应保留自己的来源校验与结果清单。

## 脱敏导出

```bash
python scripts/supplement/analyze.py runs/metadata_supplement/development runs/metadata_supplement/evaluation
python scripts/supplement/audit_calendar.py runs/metadata_supplement/evaluation
```

`analyze.py` 比对请求、响应、轨迹、工具执行与模拟前后状态，保留来源 SHA256，只导出指标与校验。`audit_calendar.py` 是发现评分问题后增加的事后事实检查，不能作为预注册的主指标。

原始对话、请求、响应、模拟后端状态、模型权重与密钥均保留在被忽略的私有目录。
