# Formal experiment shard

Five shards have been completed and verified against the common format and frozen version with each shard containing 336 items totaling 1,680 items. Each shard includes all seven configurations and each task runs on the same platform making it impossible to treat platform differences as configuration differences.

| shard | Task ID | Normal / Output Attack / Instruction Attack | Actual platform |
|---|---|---|---|
| 1 | 0, 12, 17, 31 | 84/126/126 | Vanda |
| 2 | 2, 7, 22, 32 | 84/126/126 | macOS |
| 3 | 16, 24, 27, 35 | 84/126/126 | WSL |
| 4 | 3, 8, 18, 28 | 84/126/126 | Vanda |
| 5 | 5, 9, 30, 33 | 84/126/126 | Vanda |

Frozen list located at `assignments/formal/plan.json`, single shard list is `person-01.json` to `person-05.json`.De-identified raw metrics are located at `experiments/deliveries/`, common statistics are available at [formal results](../results/formal/README_ZH.md).

Planned time is used only for pre-run allocation; final performance interpretation adopts [measured overhead and platform layering](../results/formal/overhead/README_ZH.md).Reproduction should use a new directory with a new run ID and retain new sampling results; published data will not be overwritten. Run entry point is at [formal experiment instructions](FORMAL_START_ZH.md).
