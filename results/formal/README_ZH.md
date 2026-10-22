# Formal experiment summary

`analysis.json` by `scripts/formal/summarize.py` reading five de-identified data sets to generate, totaling 1,680 records, covering 20 tasks, seven configurations, and three repetitions. Historical MVP, development validation, and offline script responses are separately counted.

Original public measurements located at `experiments/deliveries/person-01/` to `person-05/`.[data list](manifest.json) records file hash, run platform, sample count, and API return cost for each data set.

[Result table and six core charts](analysis/README_ZH.md) show security, normal task completion rate, pairing differences, component ablation, per-task performance, and resource usage across seven configurations. Each chart provides PNG and PDF; machine-readable tables located at `analysis/tables/`.

## Data scope and experimental limitations

- Retain one `TimeoutError` and all rejections, call limits, and task failures. Timeout cannot be considered defense success.
- Data sets 1, 4, and 5 run on Vanda; data set 2 runs on Mac; data set 3 runs on WSL. Mac uses native CPU Torch 2.7.1, others use 2.7.1+cu126; model weights and frozen core algorithms are identical. Numerical values and latency may differ across hardware; runtime analysis must be stratified by platform.
- Trial 151 in shard 2 resumed using cached responses. Some historical API timings use file timestamps; latency analysis must also report sensitivity excluding this trial.
- In shard 3, `wall_seconds` is the sum of case durations, not the continuous worker wall-clock time.
- Returned API responses report **$3.07556061** in total. One timed-out request in shard 3 returned no provider cost, so its final charge is unknown. The original $0.05 was a client reservation; releasing it does not establish final provider billing reconciliation.
- `complete=true` indicates complete record count. Task success rate, attack success rate, and safe completion rate are reported separately; runtime errors are retained in the planned sample denominator, with effective record count specified separately. Results are explained by task, configuration, and attack surface.

## Reproduction summary

Run the following commands on the Vanda PBS computing node and in the repository root directory. Data validation and aggregation do not invoke model APIs:

```bash
python scripts/validation/check_deliveries.py
python tasks/02/prepare_delivery.py --check --require-validated
python scripts/formal/summarize.py --plan assignments/formal/plan.json \
  --deliveries experiments/deliveries --output runs/validation/analysis.json
```

[52 key records reviewed](review/README_ZH.md) provides per-record cause classification, actual protection mechanisms, and scoring limitations. This targeted review does not replace full-scale formal statistics.

[Tool instruction attack diagnosis](metadata_diagnosis/README_ZH.md) Five sets totaling 180 derived checks have been verified. 90 groups of unprotected versus TrustGate comparisons have been organized, distinguishing between identical-named tool invocations and precise attack targets, and providing offline control for target executability and the scorer.
