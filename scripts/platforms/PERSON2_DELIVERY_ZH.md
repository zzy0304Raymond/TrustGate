# 第2人Mac交付说明

原始实验基于30ff955的冻结源与本地配置运行。scripts/platforms/local目录保留了当时配置的完整快照；其中README的“仅配置、未启动”描述属于开跑前的历史状态。当前完成状态以tasks/02/PROGRESS.md及experiments/deliveries/person-02/为准。

- person2_supervisor.py：原批次进度与脱敏导出。
- person2_resume.py：用户明确暂停后，经无API逐请求验证缓存的有界续跑。旧批次不覆盖；总2美元上限包含此前费用。
- tasks/02/prepare_delivery.py：整理与核验交付，不调用模型API。

原始运行目录、准备指纹、暂停记录、缓存和账本仍保存在私有runs/。不要为重现结果删除claim或重跑整份。原运行环境配置包含原HEAD；提交后HEAD改变不代表原运行记录被篡改，复核已发生运行应使用保存的原始版本与清单，不重新启动旧命令。

标准receipt字段只保证交付格式，不表示已经完成Vanda验收。实际Mac/CPU依赖和本地适配及恢复代码的hash均随包披露，须全组审核。
