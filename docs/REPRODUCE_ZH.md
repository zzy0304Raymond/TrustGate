# Installation, execution, and reproduction

## 1. Get the code

```bash
git clone https://github.com/zzy0304Raymond/TrustGate.git
cd TrustGate
```

The reference environment uses Python **3.10.20** and the Conda environment `dsa4213`. On Vanda, installation, computation, and validation must run through PBS. Login nodes are for scheduling, editing, inspection, and Git operations. CPUs are sufficient; these jobs do not need GPUs.

## 2. Install dependencies

Use the existing reference environment if available. Otherwise, create the environment inside an allocated compute session after loading your own Conda installation:

```bash
source /path/to/your/load-conda.sh
conda create -n dsa4213 python=3.10.20 pip
conda activate dsa4213
python -m pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu126
python -m pip install -c requirements-runtime-constraints.txt -r requirements.txt
python -m pip install -c requirements-runtime-constraints.txt -r requirements-analysis.txt
python -m pip check
```

`requirements-runtime-constraints.txt` pins runtime dependencies. The frozen experiment manifest additionally checks six key package versions. The reference Torch build is `2.7.1+cu126`, although inference runs on CPUs. The older `requirements-agentdojo.lock` and `requirements-mvp.lock` record installation history and must not override the final constraints. Plotting dependencies are listed separately from runtime dependencies.

Recomputing public statistics requires only the Python 3.10.20 standard library: no API key, detector weights, or full runtime dependencies. Plotting additionally requires `requirements-analysis.txt`. Model and MCP execution require the full environment.

## 3. Reproduce public statistics without API calls

On a personal computer or inside an allocated compute session:

```bash
export PYTHONHASHSEED=0
python scripts/reproduce.py --output runs/reproduce
```

On Vanda, submit from the repository root:

```bash
export TRUSTGATE_CONDA_LOADER=/path/to/your/load-conda.sh
qsub -P personal-YOUR_ACCOUNT -v TRUSTGATE_CONDA_LOADER scripts/reproduce.pbs
```

This entry point verifies the five trial CSVs, frozen source identities, case coverage, scoring denominators, diagnostic evidence, and demo inputs. It rebuilds the main and overhead tables from public records and compares them byte for byte with the published tables. The English release map verifies translated files against their recorded revisions while preserving original experiment identities; see [artifact integrity](ENGLISH_RELEASE.md).

Direct execution writes to `runs/reproduce/`. The PBS wrapper writes to `runs/reproduce-JOB_ID/`, including `run.log`, regenerated results, and `verification.json`. Neither reads an API key nor calls a model.

Add `--plots` to rebuild the six figures. With PBS, set `TRUSTGATE_PLOTS=1` and include it in `qsub -v`. PDF creation timestamps are not experiment measurements; the numeric tables are the objects compared byte for byte.

## 4. Prepare the pinned detector

Download on a compute node. Only the initial download needs network access:

```bash
python experiments/mvp/prepare_detector.py
export TRUSTGATE_DETECTOR_DIR="$PWD/models/prompt_injection_detector"
```

`models/detector_revision.txt` specifies the revision. The formal manifest pins SHA256 hashes for six model files. To reuse an existing cache, set its absolute path. Model weights are excluded from Git.

## 5. Run full offline validation

```bash
export TRUSTGATE_CONDA_LOADER=/path/to/your/load-conda.sh
export TRUSTGATE_DETECTOR_DIR=/path/to/frozen/prompt_injection_detector
export TRUSTGATE_FULL_CHECK=1
export TRUSTGATE_PLOTS=1
qsub -P personal-YOUR_ACCOUNT \
  -v TRUSTGATE_CONDA_LOADER,TRUSTGATE_DETECTOR_DIR,TRUSTGATE_FULL_CHECK,TRUSTGATE_PLOTS \
  scripts/reproduce.pbs
```

Full mode also runs the regression suite, dependency checks, adaptation checks for 24 tools, transport and goal-reachability checks for 60 attacks, permissions for 20 tasks and seven configurations, benign-description and reference-call false-positive checks, eight paired transport controls, and six MCP demo controls. Model responses in mechanism controls are scripted; these checks produce no new LLM effectiveness observations.

Inside an allocated PBS session, use `python scripts/reproduce.py --full --plots --output runs/reproduce-new`. Choose a new output directory for full mode to preserve earlier control records. Do not fabricate PBS variables to bypass cluster rules.

## 6. Repeat the model experiments

Store an authorized OpenRouter credential in a private file, set its permissions with `chmod 600`, and point `TRUSTGATE_KEY_FILE` to that file. The process environment variable `OPENROUTER_API_KEY` is also supported. Keep key values out of command arguments, Git, and PBS export arguments.

| Study | Frozen manifest | Entry point |
|---|---|---|
| Original formal study: 1,680 trials | `assignments/formal/plan.json` | [Five formal shards](FORMAL_START_ZH.md) |
| Metadata supplement: 156 trials | `assignments/metadata_supplement/` | [Supplement instructions](../scripts/supplement/README_ZH.md) |
| Transport validation: 48 trials | `assignments/transport_validation/plan.json` | `scripts/transport/run.pbs` |

Use a fresh checkout and new run identifier. Reuse the published manifests without selecting new tasks or templates. Core source, model, and key dependency checks must pass. Retain failures and timeouts; infrastructure errors are not retried automatically. New samples must not overwrite the measurements under `results/`.

The transport launcher exports new statistics to `runs/transport_validation/export/`. An independent export can also use:

```bash
python scripts/transport/export_run.py \
  --run runs/transport_validation/live \
  --controls runs/transport_validation/live-controls \
  --output runs/transport-validation-export-new
```

Set the Vanda project, Conda loader, credential path, and detector path for your own account. Pass `TRUSTGATE_KEY_FILE,TRUSTGATE_DETECTOR_DIR,TRUSTGATE_CONDA_LOADER` to the transport entry point. Configure the Conda loader in the supplement launcher for your environment. Other clusters must use their actual scheduler allocations; see [cross-platform requirements](CROSS_PLATFORM_CHECKLIST_ZH.md).

## 7. Present the demonstrations

Download `demos/index.html` and open it in a browser, or run `python scripts/demo/show.py` for a terminal replay. Full validation already includes the MCP mechanism controls. See the [demo guide](../demos/README_ZH.md).
