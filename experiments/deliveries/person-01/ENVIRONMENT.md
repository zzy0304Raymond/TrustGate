# person-01 runtime environment

- Platform: Vanda; scheduler: PBS; job `1462633.stdct-mgmt-02`; node `CN-016`.
- Operating system: Red Hat Enterprise Linux 9.4;`Linux-5.14.0-427.134.1.el9_4.x86_64-x86_64-with-glibc2.34`.
- CPU: Intel(R) Xeon(R) Platinum 8452Y; requested 2 CPU, 8 GB memory, 6 hours; PBS actually allocated 2 CPU, 13 GB memory.
- GPU: not requested, not used; detector runs on CPU.
- Conda: `dsa4213`; Python `3.10.20`; using existing frozen environment, no dependencies installed or upgraded.
- Git base commit at startup:`92888fc2fbd09ef967f1af25a657df94d3e42d56`; branch `experiment-1`. Personal added startup and logging scripts not yet committed at startup; their SHA-256 stored separately in private environment record; frozen execution code and list are consistent.
- Final list SHA:`b1817378e174e1cd742acedc465e63620a1dbe3bdbdca92c86c70d26d01f42c6`.
- Run ID:`formal-v1-001`; shard:`shard-00`; personnel:`person-01`.
- Current status: 336/336,`complete=true`, `fatal_error=null`.
- Actual reported API cost: $0.71732400.
- PBS start: 2026-10-16 23:08:25 SGT; end: 2026-10-17 02:04:04 SGT; PBS recorded wall-clock time 2 hours 55 minutes 38 seconds.
- Formal executor timing: 10,415.43 seconds (approximately 2 hours 53 minutes 35 seconds); rest is overhead from checks and exports.
- Cost ledger has no pending or unknown costs, no budget stop triggered; above cost is solely for this formal experiment, not cumulative shared API account cost.

## Key dependencies

- `agentdojo==0.1.35`
- `mcp==1.26.0`
- `transformers==4.53.3`
- `torch==2.7.1+cu126`
- `pydantic==2.14.1`
- `openai==3.31.0`

## Model and startup

- API: `qwen/qwen3-30b-a3b-instruct-2507`, supplier `SiliconFlow`, temperature=0.
- Detector:`protectai/deberta-v3-base-prompt-injection-v2`, threshold 0.5; model file hash verified through frozen list check.
- Python startup configuration `PYTHONHASHSEED=0`, `TOKENIZERS_PARALLELISM=false`, `OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2`.
- Personal entry point:`qsub tasks/01/run_person01.pbs`The script uses a private Group 9 key file path without including the key value.
- Perform offline checks first at the entry point, then invoke the original repository. `scripts/formal/person-1.pbs`, run only shard-00, then invoke the original export tool after completion.
- Public executor, tasks, attacks, models, dependencies, and official manifests remain unchanged. New code only records personal environment, passive monitoring costs, and schedules checks/export.
- This API budget is $2, with $0.05 reserved per request. Passive monitoring writes cost alert files and logs at $1.50, requiring monitoring personnel to read and query users; the script does not send notifications automatically. Frozen executor retains original budget stop behavior and no automatic resumption limit. After $2, further continuation requires separate review and directory deletion for rerun is not allowed.

## Validation and recording

- `pip check`, 33 offline unit tests, MVP MCP pre-check, parsing recovery check, and official MCP pre-check all pass before starting the API experiment.
- Official pre-check includes 60 attack transmission checks, 20 task flow checks, 14 configuration/entry flow checks, using script responses, and does not count toward official model results.
- Source code, critical dependencies, and detector hashes are verified by the original frozen validator.
- The original export tool has verified that 336 trial IDs exactly match the personal list with no duplicates or omissions; including 84 normal experiments, 126 output attacks, and 126 instruction attacks. Records of task errors, rejections, and exhausted single-call attempts are preserved as-is; complete records do not imply the model answered all correctly.
- Private prep logs and machine-readable environment records:`runs/person01-preparation/1462633.stdct-mgmt-02/`.
- Private official records:`runs/studies/formal-v1-001/shard-00/`, fully preserved without submitting original requests simulated states or keys.
