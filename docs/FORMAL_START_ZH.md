# Repeat the frozen formal study

The published study is complete and contains 1,680 trials. These commands generate a new model sample from the fixed design. To reproduce statistics or demonstrations, use the [API-free reproduction entry point](REPRODUCE_ZH.md).

## Design and environment

`assignments/formal/plan.json` fixes 20 tasks, 60 attacks, seven configurations, and three repetitions. Each of the five shards contains 336 trials: 84 benign, 126 output-injection, and 126 metadata-injection trials. Every shard includes all configurations. See the [shard allocation](TEAM_PLAN_ZH.md).

Clone a fresh `main` checkout and follow the [installation guide](REPRODUCE_ZH.md) for Python 3.10.20, pinned dependencies, and the detector. Execution verifies core source identities, dependencies, weights, cases, and initial states. Do not regenerate a manifest to bypass a mismatch.

## Submit to Vanda PBS

Set paths and a new run identifier from the repository root. The credential file must belong to your account with mode 600. Pass only its path in arguments.

```bash
export TRUSTGATE_RUN_ID=replication-001
export TRUSTGATE_CONDA_LOADER=/path/to/your/load-conda.sh
export TRUSTGATE_KEY_FILE=/absolute/private/openrouter_group9.key
export TRUSTGATE_DETECTOR_DIR=/absolute/models/prompt_injection_detector
qsub -P personal-YOUR_ACCOUNT \
  -v TRUSTGATE_RUN_ID,TRUSTGATE_CONDA_LOADER,TRUSTGATE_KEY_FILE,TRUSTGATE_DETECTOR_DIR \
  scripts/formal/five_people.pbs
```

The array job requests five independent CPU shards, each with 2 CPUs, 8 GB memory, and up to six hours. It does not request GPUs. Actual concurrency and queue time depend on the scheduler. Each shard retains the original client stop budget of $2, or $10 for all five; runtime is not guaranteed.

Alternatively, submit `scripts/formal/person-1.pbs` through `person-5.pbs` separately with the same variables and a new run identifier. Choose either the array or individual jobs to avoid duplicate execution.

## Collect and summarize results

Shard outputs are under `runs/studies/replication-001/shard-00/` through `shard-04/`. Existing directories are not overwritten. Denials, task failures, call limits, and infrastructure errors are retained. Infrastructure failures do not trigger automatic model retries.

After all five shards finish, summarize on a compute node:

```bash
python -m trustgate merge \
  --plan assignments/formal/plan.json \
  --run-root runs/studies/replication-001
python scripts/formal/summarize.py \
  --plan assignments/formal/plan.json \
  --merged runs/studies/replication-001/merged/results.json \
  --output runs/studies/replication-001/analysis.json
```

For an incomplete run, use merge's `--allow-partial` flag to inspect progress. The output remains marked incomplete. `complete` means record coverage, not success on every user task.

Example sanitized export:

```bash
python -m trustgate export \
  --plan assignments/formal/plan.json \
  --worker-dir runs/studies/replication-001/shard-00 \
  --destination runs/export/person-01
```

Keep new results separate from the published `experiments/deliveries/` and `results/`. Original requests, complete simulated states, and credentials remain private. The unified reproduction entry point recomputes the original published statistics directly. See the [overhead analysis](../results/formal/overhead/README_ZH.md) for platform and timing definitions.

For another platform, first follow the [compatibility requirements](CROSS_PLATFORM_CHECKLIST_ZH.md). Vanda is the reference validation environment. Do not fabricate a PBS job environment.
