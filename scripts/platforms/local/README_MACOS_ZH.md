# experiment-2 local configuration

This directory serves as an independent execution entry for macOS arm64. Currently only configuration and offline verification are performed, no formal trials have been initiated, and no paid model APIs have been invoked.

## file location

- `person2.sh`: startup entry point with fixed random seed CPU threads and project Python environment
- `person2.py`: local adapter for user 2 reusing original experiment loop data strategy and MCP services without emulating PBS environment
- `requirements.txt`, `constraints-macos.txt`: local dependency configuration
- `tests_local.py`: offline checks including duplicate startup prevention network failure billing stop and data de-identification export
- repository root directory `.venv/`: Python 3.10.20 experimental environment
- repository root directory `.runtime/`, `.bootstrap/`: environment manager Python installation and download cache stored locally only
- repository root directory `models/prompt_injection_detector/`Fixed revision detector file verified against original list.
- repository root directory `.secrets/openrouter_group9.key`: private credentials, readable and writable only by their owner; excluded from Git.
- repository root directory `runs/local-person2/execution.json`Local configuration fingerprint for this session.
- repository root directory `runs/local-person2/offline-check.json`Offline validation results, not official model experiment results.

## Retained experiment settings

Run only original `assignments/formal/plan.json` the 2nd copy (index 1), 336 IDs in original order: 84 normal, 126 output attacks, 126 instruction attacks. Model, SiliconFlow provider, temperature, seven configurations, number of repetitions, detector threshold, and weights are retained.

API stop budget 2 USD, reserving 0.05 USD per request; stops on unknown costs or network failure without automatic retry. Failed records are retained. Ready batch can be claimed only once, no automatic resumption supported, prohibited to repeat the entire batch after record deletion.

## platform differences

Original frozen source code data and plan have not been modified; Vanda’s PBS entry is retained. Mac uses CPU `torch==2.7.1`, the original platform is `2.7.1+cu126`; other critical package versions are the same. Platform-specific adapters are validated separately, retain their own configuration fingerprints, and cannot be directly treated as original environment results passed by Vanda. Platform version coordination across the entire team and acceptance testing are still required before formal merging.

Local export uses `local-receipt.json`, does not generate `receipt.json`.

## configuration check (does not invoke model API)

Run at the repository root directory:

```bash
bash scripts/platforms/local/person2.sh status
bash scripts/platforms/local/person2.sh check
```

Offline testing:

```bash
PYTHONHASHSEED=0 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  .venv/bin/python scripts/platforms/local/tests_local.py
```

## Use this for future explicit startup

The following commands will invoke the model API; this command was not executed in the current configuration.

```bash
bash scripts/platforms/local/person2.sh run --run-id local-person2-20261019-001
```

Keep the machine awake and maintain stable network connection. Do not modify the configuration or experiment files during execution. Progress and complete private trajectory are saved in `runs/studies/<Run ID>/shard-01/`. In another terminal, run `status` Check progress in another terminal. In case of interruption, cost, or network error, retain all records and determine the next steps separately without re-executing the entire task.

After completion, export as needed to a separate local delivery directory:

```bash
bash scripts/platforms/local/person2.sh export \
  --folder runs/studies/local-person2-20261019-001/shard-01 \
  --destination experiments/deliveries/person-02-local
```

Prepare, check, and status commands will not initiate model trials.`account` Optional read-only API identity checks were also not executed this time.
