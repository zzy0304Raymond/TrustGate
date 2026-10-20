# Person 03 actual runtime environment

- Platform: Linux / local adapter (WSL when kernel release contains microsoft).
- Kernel: 6.6.87.2-microsoft-standard-WSL2
- Python: 3.10.20
- Git base commit: 80e05a3e8b6d7597791aa0ea5ee65c6e3d2ddc2a
- Extra executable adapter: see adapter_sha256 in platform_receipt.json.
- Frozen plan SHA256: b1817378e174e1cd742acedc465e63620a1dbe3bdbdca92c86c70d26d01f42c6
- Run ID: formal-v1-001
- Shard/person: 2 / 3; expected trials: 336.
- Scheduler: none; PBS_JOBID was not set or fabricated.
- Detector inference: CPU; no GPU requested by the experiment.
- Hardware: {"cpu_model": "Intel(R) Core(TM) i9-14900HX", "logical_cpus": 32, "memory_total": "7985272 kB"}
- Thread settings: {"MKL_NUM_THREADS": "2", "OMP_NUM_THREADS": "2", "PYTHONHASHSEED": "0", "TOKENIZERS_PARALLELISM": "false"}
- Packages: {"agentdojo": "0.1.35", "mcp": "1.26.0", "openai": "3.31.0", "pydantic": "2.14.1", "torch": "2.7.1+cu126", "transformers": "4.53.3"}
- Launch: python scripts/platforms/local/run.py --execute --detector-dir <pinned-cache> --run-id <above-run-id>
- Completion: True; recorded: 336
- Budget ledger: {"halted": false, "limit_usd": 2.0, "pending_reserved_usd": 0.0, "per_request_reservation_usd": 0.05, "reported_cost_usd": 0.51220968, "uncertain_reserved_usd": 0.05}
- Environment, frozen source/package/model verification runs before API access.
- Offline verification reports: runs/local-offline/ (private; retain for review).
- Vanda validation: NOT performed by this adapter. Team acceptance remains separate.
- Full traces, credentials and simulated backend state remain private.

## Final submission accounting

- Formal API cost is approximately $0.51; approximately $0.52 including the separate development probe.
- Exact returned formal usage remains $0.51220968, matching the CSV. The owner approved approximate cost reporting and release of the old client reservation for submission.
- ACCOUNTING.json preserves the original execution accounting and the explicit reporting adjustment; no trial costs, outcomes or private ledger were rewritten.
- Full 336-row CSV is byte-identical to the earlier review bundle after LF canonicalization; one TimeoutError and 12 model_call_budget records remain.
- receipt.wall_seconds is summed case seconds across attempts, excluding startup, export and user pauses; it is not continuous worker wall time.
- Supplementary audit: python tasks/03/audit_delivery.py --accept-estimated-costs
- Prepared for team review; Vanda validation and merge approval remain pending.
