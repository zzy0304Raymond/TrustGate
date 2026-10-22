# Five-person cross-platform execution and merge checklist

The platform sources and dependency differences for this round’s five datasets are as follows [Formal results explanation](../results/formal/README_ZH.md). Mac uses native CPU Torch build; this difference is retained in the data checklist. The following checklist serves as the common baseline for reproducing experiments.

**The preliminary configuration and completed validation of this project are based on Vanda, and the final acceptance environment for code and results is also Vanda.** Five individuals may use different computing environments, but the delivered public code must preserve Vanda’s execution method, and results must be readable by the same verification and aggregation procedures on Vanda. The current repository has not yet completed execution validation on other platforms such as NSCC; Vanda’s paths and job scripts cannot be directly copied over.

Here, ’compatibility with Vanda’ includes two aspects: code must pass inspection and run successfully on Vanda’s PBS compute nodes; results generated on other platforms must retain their true origin, delivered in a unified format, and verified through version, task identity, and integrity checks. **There is no need to rewrite results from other platforms as if they were run on Vanda, nor is it required that the five machines produce identical model responses word-for-word.**

## 1. First, the five individuals confirm their respective

| personnel | Git branch | Shard directory | Delivery directory | Formal task IDs |
|---|---|---|---|---|
| 1 | `experiment-1` | `shard-00` | `person-01` | 0, 12, 17, 31 |
| 2 | `experiment-2` | `shard-01` | `person-02` | 2, 7, 22, 32 |
| 3 | `experiment-3` | `shard-02` | `person-03` | 16, 24, 27, 35 |
| 4 | `experiment-4` | `shard-03` | `person-04` | 3, 8, 18, 28 |
| 5 | `experiment-5` | `shard-04` | `person-05` | 5, 9, 30, 33 |

Each person completes 336 trials: 84 normal experiments, 126 tool output attacks, and 126 tool instruction attacks. Each trial includes all seven configurations with three repetitions. Five assignments total 1,680 trials; do not repeat trials, and do not add development set or historical MVP results to meet the count.

## 2. Each person must check before starting

- [ ] **The same formal list.** Use the repository’s [plan.json](../assignments/formal/plan.json) and the corresponding `person-NN.json`do not regenerate tasks, attacks, permissions, or trial sequences on your own. `plan_sha256` is `b1817378e174e1cd742acedc465e63620a1dbe3bdbdca92c86c70d26d01f42c6`; if a unified version update occurs in the future, the newly released list shall prevail.
- [ ] **Same experiment code.** The code in the frozen list `source_sha256` must be consistent with the local code. Different branches may have different document submissions and result submissions, so it is not required that the five branches have identical Git commits; record the actual commits for each branch and ensure the frozen running code is identical.
- [ ] **Same Python and dependencies.** Python is `3.10.20`, [environment instructions](REPRODUCE_ZH.md) and [dependency constraints](../requirements-runtime-constraints.txt); key package versions must match the manifest field `packages` The current Torch build is `2.7.1+cu126`, do not manually switch to another build or upgrade dependencies.
- [ ] **Same baseline and data.** Use AgentDojo `v1.2.2` Workspace suite, and the frozen 20 tasks, 60 attack cases, and permissions; each trial uses an independently initialized state created by the program, without copying email, calendar, or file states from prior runs.
- [ ] **Same API model and vendor.** The model is `qwen/qwen3-30b-a3b-instruct-2507`, supplier is `SiliconFlow`, `temperature=0`.Cannot switch models or use local GPU models. Use the authorized key provided by this group. The key will not be included in Git.
- [ ] **Same detector.** Use `protectai/deberta-v3-base-prompt-injection-v2`, model file hash matches the one in the manifest `detector_sha256` , threshold `0.5`, maintain current CPU inference method.
- [ ] **Same trial constraints.** Each trial allows up to 8 model calls, up to 1,024 output tokens per call, 180 seconds task time limit, and up to 3 rejection attempts; each configuration is repeated 3 times. Parameters see [official configuration](../configs/formal/frozen.json), execute according to the configurations listed within.
- [ ] **The same seven configurations.**`none`, `delimiters`, `classifier`, `trustgate`, `no_provenance`, `no_metadata`, `no_authorization` Keep all configurations, not just the ones with good performance.
- [ ] **The same startup convention.** Set before starting Python `PYTHONHASHSEED=0`, `TOKENIZERS_PARALLELISM=false`; maintain existing scripts’ `OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2`. The current five-person unified experiment ID is `formal-v1-001`, each runs only their own shard.
- [ ] **The same cost and failure handling.** Each person’s API stop budget is $2, the whole group’s is $10, and each request reserves $0.05; this is client-controlled, not a billing guarantee. Keep failures, timeouts, rejections, and infrastructure errors; do not delete existing directories and rerun, nor repeatedly retry until success.
- [ ] **Check before formal execution.** Execute on the assigned compute node after completing [environment instructions](REPRODUCE_ZH.md) the no-API check including `python scripts/formal/preflight.py`, then proceed with [start instructions](FORMAL_START_ZH.md) submitting your own assignment. If there are errors in the checklist, code, dependencies, model files, or initial state during startup, resolve the causes first.

`python -m trustgate inspect --plan assignments/formal/plan.json` You can check the checklist and display its SHA and shard count; it cannot replace a full runtime environment check. The formal executor will check frozen code, critical dependencies, and detector files before calling any API.

## 3. How to switch to NSCC or other environments

**Different projects are allowed:** cluster name, account, repository absolute path, Conda location path, model cache path, private key file path, job queue, and compute node model that meets resource requirements. Different environment paths themselves do not prevent result merging.

**Current execution method:** large model via remote API call, local detector running on CPU; personal assignments in the repository default to 2 CPUs, 8 GB memory, and 6 hours wall clock time, without GPU allocation. Switching to a GPU-equipped machine will not automatically enable GPU usage for the current experiment, nor should the model or detector execution method be changed because of this.

Handle platform differences in the following order:

1. **First confirm the scheduler used by the platform and installable versions.** The current executor requires the actual PBS job environment’s `PBS_JOBID`. If the target environment uses a different scheduler, the existing code cannot run directly; do not fake this variable or remove the check.
2. **When only path or job resource adjustments are needed, provide a separate platform startup script.** Suggested location: `scripts/platforms/<platform name>/`, clearly specifying environment activation, path variables, and submission method; retain the Vanda entry under `scripts/formal/` . Public Python code, checklist, data, and result formats remain unchanged. This directory is recommended for adapter code but does not indicate the repository already provides an NSCC adapter.
3. **If modifications to the executor, dependency versions, or model execution method are necessary, first unify the public version.** Document the changes, retain the Vanda run path, perform offline validation between Vanda and the target platform, then publish a new frozen checklist and synchronize it with five people. When API validation is needed, use only clearly defined quantities and budgets for development validation, keeping results separate from formal testing. Do not have five people each modify code and then directly start formal experiments.
4. **After version changes, first determine which experiments are affected.** Old records remain unchanged and are kept separate from new versions; re-runs use clearly defined scope, budget, and new run numbers. Do not use modified `receipt.json`, checklist SHA, or source code SHA to make inconsistent results pass merging.
5. **Return to Vanda acceptance before delivery.** Platform-specific startup scripts may be retained, but shared code must still be executable via Vanda’s PBS entry, and exported results must be successfully read and aggregated by the common version on Vanda.

CPU performance, network, and API queuing differences across platforms affect runtime. Report actual platform and runtime in the report; when analyzing cross-platform latency, explain these differences, and do not directly attribute raw speed differences to the defense method.

## 4. What each person needs to deliver

- [ ] Keep the private run directory fully intact, including actual runtime configuration,`manifest.json`, `worker_summary.json`, cost records, and failure records. Complete dialogues, original requests, and simulated states are not submitted to Git.
- [ ] I have 336 unique experiment IDs with no duplicates or omissions;`worker_summary.json` in `complete=true` and `fatal_error=null`. This indicates complete recording, not that all 336 tasks were successful.
- [ ] Use the repository export tool to generate `experiments/deliveries/person-NN/results.csv` and `receipt.json`, do not manually modify column names, experiment identity, version fields, or scores. Specific commands are in [start instructions](FORMAL_START_ZH.md).
- [ ] Supplement within the same delivery directory `ENVIRONMENT.md`, clearly stating actual cluster, operating system, CPU/GPU and actual usage, scheduler, Python/critical dependency versions, Git commit, list SHA, run number, shard number, startup script, and keyless startup method, platform changes, and check results. Paths containing account information may be sanitized; do not include keys or access tokens.
- [ ] If platform adaptation code exists, submit the script and description together, specifying the Vanda verification method and results; unverified items must be clearly marked.
- [ ] Submit only to my own `experiment-N` branch, deliver my results and description, update task progress, and initiate a PR. After five submissions, team members will review and merge, avoiding overwriting others’ delivery directories.

`ENVIRONMENT.md` This is manually filled environment description, not auto-generated by existing export tools, nor a substitute for auto-generated `receipt.json`.

## 5. How to verify on Vanda

The person responsible for aggregation collects all five deliveries and operates on the **PBS compute nodes assigned by Vanda**:

1. Use the jointly released code and official list to activate the Python 3.10.20 `dsa4213` environment. If platform adaptation or public code changes are included, complete offline checks as per [environment instructions](REPRODUCE_ZH.md), confirm that Vanda’s PBS run entry remains valid; development verification requires a separate bounded list and budget.
2. Verify the five `ENVIRONMENT.md` and export credentials: personnel and shard correspond one-to-one, list and source code versions match, each `recorded=336`, `complete=true`, and confirm that each export was generated from a complete run without fatal errors. The aggregation script cannot replace verification of environment and completion status.
3. Place the five `person-NN` folders into `experiments/deliveries/` then run from the repository root:

```bash
source /scratch/xinqi.chen/load-conda.sh
conda activate dsa4213
export PYTHONHASHSEED=0 TOKENIZERS_PARALLELISM=false
python -m trustgate inspect --plan assignments/formal/plan.json
python scripts/formal/summarize.py \
  --plan assignments/formal/plan.json \
  --deliveries experiments/deliveries \
  --output results/formal/analysis.json
```

4. Verify output is `planned=1680`, `recorded=1680`, `complete=true`. The program checks the delivered list and source code credentials, as well as duplicate, foreign, or identity-mismatched experiment records; incomplete records prevent treating the aggregation as a complete formal conclusion.
5. Retain source platform, cost receipts, error logs, and final aggregation. After team member review, merge the five experiment branches into `main`.

Different hardware and API time slots may affect model output and runtime. Final results retain platform sources; task success rate is calculated per item; platform and timing constraints are in [Formal results explanation](../results/formal/README_ZH.md).
