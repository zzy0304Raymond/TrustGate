# Mac 实验来源与恢复

第 2 份正式数据已完成，权威记录为 `experiments/deliveries/person-02/`。其 336 个 ID、冻结核心源码与总体清单已统一核验。

本地适配使用 CPU Torch 2.7.1；Vanda 使用 2.7.1+cu126，差异保留在来源说明中。第 151 条记录复用了五个相同请求的缓存响应；总调用预算仍为八次，原目录未覆盖。部分历史 API 时间来自文件时间，最终 [开销分析](../../results/formal/overhead/README_ZH.md) 同时排除此条作敏感性比较。

`person2_supervisor.py`、`person2_resume.py` 和 `tasks/02/prepare_delivery.py` 保留原运行与导出逻辑。完整请求和状态不公开；公开 CSV、收据、恢复说明及哈希可独立核验。新的系统复现优先使用 [统一入口](../../docs/REPRODUCE_ZH.md)，不要重新启动原已完成目录。
