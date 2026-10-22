# Local tools compared with MCP

48 real model validations under fixed checklist completed independently from original 1,680 formal studies. Six categories of normal tasks 36 items, two existing output attacks 12 items; local and MCP use same model, tools, payload, initial state and budget, three trials per cell.

| Scenario | entry point | Valid/Preset | Native task success | Attack succeeds | Attack exposure | Average seconds |
|---|---|---:|---:|---:|---:|---:|
| benign | local | 18/18 | 15/18 | — | — | 24.47 |
| benign | mcp | 18/18 | 12/18 | — | — | 25.04 |
| output | local | 6/6 | 3/6 | 2/6 | 6/6 | 23.47 |
| output | mcp | 6/6 | 4/6 | 1/6 | 6/6 | 20.92 |

In 24 paired groups, native task outcomes matched 18/24; output attack outcomes matched 3/6. Per-pair IDs and differences see `pairs.csv`.

Eight preset response checks passed: local/MCP tool definitions, model-visible trajectories, read results, payload injection, and pre/post states fully consistent. This validates adaptation implementation; outcome comparisons of real models reflect this batch sample and do not imply statistical equivalence.

This batch is entirely unshielded and adapted for isolated transmission. The original input injection is achieved through an independent thin adapter to achieve the same one-append behavior as MCP; the official executor and 1,680 scores remain unchanged. Preset reply checks are not included in the above 48 real model trials.

This batch’s backup official task and existing attacks are post-adaptation diagnostic checks, not new generalization tests. A model temperature of zero does not guarantee identical responses; adjacent pairs and random intra-order cannot fully eliminate service fluctuations. Duration includes tool selection path and remote response time and cannot be considered pure MCP protocol overhead.

Attempted request count for this batch is 178; valid records and actual duration are shown `summary.json`. All failures are retained.

## Reproduction

- Unmodelled requests:`python scripts/transport/verify_public.py` Verification checklist completeness metrics and sources.
- Real MCP adaptation check: run on PBS compute nodes `python scripts/transport/study.py controls --controls runs/transport-check-new`.
- Re-run model: configure private credential path in a freshly checked-out directory, submit `scripts/transport/run.pbs`; Reuse the published list without overwriting the already run directory.

Frozen design see [PROTOCOL_ZH.md](../../assignments/transport_validation/PROTOCOL_ZH.md). Original requests, responses, and workspace states are retained in private directories, while public files contain only metrics and check hashes.
