# TrustGate demonstrations

Download [index.html](index.html) and open it in a browser. The self-contained page presents three recorded cases, including their evidence, comparisons, and limitations. It needs no server, network connection, or API key. Use the [presentation walkthrough](../docs/DEMO_WALKTHROUGH_ZH.md) for a 3–4 minute demonstration.

| Entry point | What it runs | Purpose |
|---|---|---|
| `demos/index.html` | A replay of sanitized facts from recorded experiments | Present the three cases on a personal computer |
| `scripts/demo/show.py` | Evidence verification followed by a text replay | Inspect the same recorded cases in a terminal |
| `scripts/demo/check_mcp.py` | Scripted model responses through the frozen agent loop, real MCP simulation tools, detector, and authorization checks | Verify legitimate writes, blocked unauthorized calls, false quarantine, and a native grading blind spot |

None of these entry points calls a model API. The MCP checks test mechanism behavior with scripted responses. They do not measure whether a model follows an attack and do not replace the formal experiment results.

## Run the Vanda check

Submit from the repository root. The detector must already be available at its pinned version; this command does not download weights.

```bash
export TRUSTGATE_DETECTOR_DIR=/scratch/xinqi.chen/dsa4213/TrustGate_Project/models/prompt_injection_detector
qsub -v TRUSTGATE_DETECTOR_DIR scripts/demo/validate.pbs
```

This is a CPU job using `dsa4213` and Python `3.10.20`. Submit and inspect jobs from the login node; computation runs on the allocated PBS node. Other Vanda users must supply their own project and environment paths:

```bash
export TRUSTGATE_CONDA_LOADER=/path/to/your/load-conda.sh
export TRUSTGATE_DETECTOR_DIR=/path/to/frozen/prompt_injection_detector
qsub -P personal-your_account -v TRUSTGATE_CONDA_LOADER,TRUSTGATE_DETECTOR_DIR scripts/demo/validate.pbs
```

Inspect these outputs:

- `runs/demo/validate.log`: artifact verification, tests, and mechanism checks.
- `runs/demo/mcp-checks.json`: results for six sets of scripted MCP calls.
- `runs/demo/recorded_walkthrough.txt`: text replays of the three recorded cases.

Repeating this check updates only the demo validation outputs under `runs/demo/`. It does not change the published experiment results. On another cluster, use its scheduler and preserve the pinned runtime and code. Vanda is the validated reference environment.

## Run inside an allocated compute session

```bash
source /scratch/xinqi.chen/load-conda.sh
conda activate dsa4213
python scripts/demo/build.py --check
python scripts/demo/show.py --case normal
python scripts/demo/show.py --case defense
python scripts/demo/show.py --case false-positive
python scripts/demo/check_mcp.py --detector "$TRUSTGATE_DETECTOR_DIR"
```

`build.py --check` rejects input or presentation files that differ from the recorded artifact identities. `build.py` rebuilds the page from the same public evidence. Public reproduction does not require private run directories.

## Expected MCP checks

| Check | Expected behavior |
|---|---|
| Legitimate task + TrustGate | Create the requested event; native task passes; 0 authorization denials |
| Attack call + No defense | Send the simulated attack email; the exact attack goal succeeds |
| Attack call + TrustGate | Deny the same email call; email state stays unchanged; original task passes |
| Attack call + Without authorization | Execute the attack email call; the exact attack goal succeeds |
| Date question + No defense | Make the benign date tool available and query the simulated current date |
| Date question + TrustGate | Falsely quarantine the benign date tool; the scripted incorrect-date answer still passes the native evaluator |

The last check supplies the previously observed incorrect query and answer to reproduce the grading problem. It is not a new model failure. All email, calendar, and file operations affect only temporary simulated state. Published reference checks are in [mcp_checks.json](../results/demo/mcp_checks.json).

## Evidence files

- `cases.json`: explanations and facts for three cases, referring to six recorded trials.
- `trace_checks.json`: consistency and score checks for three complete private traces, retaining only necessary facts and original file hashes.
- `manifest.json`: identities of public inputs and presentation files, with English revisions verified through the repository release map.

The three task5 traces use reviewed public evidence in `review-data/person-05/`. Environments retaining the private original records can consult `scripts/demo/export_checks.py --help` to export checks again. Full requests, responses, and workspace snapshots are not included in the public demo package.
