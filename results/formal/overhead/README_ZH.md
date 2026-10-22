# Overhead normal explanation false positives and recovery sensitivity

This analysis uses all 1,680 frozen records without adding new model requests or modifying original scores.

## TrustGate relative overhead compared to unprotected pairing

First pair by identical task, payload position, and repetition number; then average tasks equally. Exclude infrastructure errors; task failures, rejections, and call limits are still retained.

| Scenario | Pair count | Additional seconds (95% interval) | Additional model calls | Additional tokens |
|---|---:|---:|---:|---:|
| Normal task | 60 | 9.04 [6.61, 11.69] | 0.150 | 2964.2 |
| Output attack | 89 | 7.29 [4.17, 10.66] | -0.132 | 1040.3 |
| Instruction attack | 90 | 6.89 [5.23, 8.58] | 0.025 | 121.3 |

Interval is exploratory per-item interval from task clustering bootstrap (2,000 iterations, seed 421322) without multiple comparison correction. Number of repetitions is not the number of independent tasks.

## Platform and timing explanation

- `resource_by_platform.csv` List all, Vanda, Mac, and WSL together, including mean, effective mean, and median for all records.
- `paired_resources.csv` List paired differences for model calls, token count, total seconds, API seconds, detector seconds, and returned cost, as well as results after removing cached recovery records.
- Each task’s all configurations are executed by the same team member on the same platform, pairing reduces platform confounding; different platforms handle different tasks, so mean differences between platforms cannot be interpreted as hardware effects.
- Single record `seconds` It is actual task duration; do not compare total durations defined differently by different team members. Duration is affected by task path, remote services, and early termination due to failure, not a pure gateway micro-benchmark.
- Model calls and token counts only cover returned responses; original timeout records remain in full record statistics, making it impossible to estimate tokens for non-returned responses.

## Recovery and timeout sensitivity

Cache recovery log `98f0051e9f3cdb5a5daf` Part of the API timing comes from file time. All unguarded pair analyses provide both inclusive and exclusive views of this entry; when excluded, the entire affected pair is removed.
- `recovery_sensitivity.csv` Provide corresponding safety and task utility counts. Final results remain based on original full data; sensitivity results do not replace them.
- Original official single timeout cannot be counted as protective success; effective analysis excludes this entry, but the main plot of the planned denominator retains its position.

## Two types of false positives must be separated

- `metadata_false_positives.csv` Count the number of times unattacked tool instructions were isolated and check the denominator; conditions with screening disabled are marked as not applicable.
- Normal tasks repeatedly use the same 24 tool instructions; run-level check denominator does not represent an equivalent number of independent texts. See also [Distinct benign descriptions and legitimate-call checks](../false_positives/README_ZH.md).
- `benign_authorization_rejections.csv` is the rate of authorization rejection in normal tasks, including errors or over-privileged requests proposed by the model itself, which cannot be considered false positive rate.
- Legitimate call rejection rate is determined by independent offline inspection of upstream reference solutions with frozen permissions; the denominator of this ratio is legitimate calls in the reference path, not equal to all actual model-proposed manually annotated results.

## Reproduction

Running on allocated Vanda computing nodes `python scripts/formal/analyze_overhead.py --check`.
Independent replica generation available `--output runs/overhead-check`. The SHA256 and input source of this directory file are listed in `manifest.json`.
