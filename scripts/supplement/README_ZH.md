# Supplemental test entry

Design and results see [Frozen protocol](../../assignments/metadata_supplement/PROTOCOL_ZH.md) and [Results explanation](../../results/metadata_supplement/README_ZH.md). Frozen executor `study.py` Do not edit; modifications will trigger manifest validation failure. Analysis and post-hoc fact checking are independent of this executor.

## Verify delivered results

Activated on Vanda PBS compute node `dsa4213`(Python 3.10.20), execute from the repository root directory:

```bash
python scripts/supplement/verify_public.py
python -m unittest tests.test_metadata_supplement tests.test_metadata_diagnosis
```

The above operations do not invoke APIs and do not require original requests or keys.

## Re-execute frozen trials

Original execution used Vanda AgentDojo 0.1.35 and existing fixed dependencies. A frozen detector weight and model service credentials accessible to you must be available before running. Follow the environment setup instructions in the repository; different clusters only require adaptation of the job entry point. Do not modify models tools thresholds dependency versions manifests or scoring independently.

Recommended to run in a fresh checkout directory while preserving the two published JSON manifests without re-filtering templates.

```bash
mkdir -p runs
# Replace these two paths with your own private credential files and prepared detector directory.
export TRUSTGATE_KEY_FILE=/absolute/private/openrouter_group9.key
export TRUSTGATE_DETECTOR_DIR=/absolute/models/prompt_injection_detector
qsub -v TRUSTGATE_KEY_FILE,TRUSTGATE_DETECTOR_DIR scripts/supplement/run_vanda.pbs
```

`run_vanda.pbs` According to `PBS_O_WORKDIR` Enter the repository, project account, and resources must be adapted to your personal Vanda account. It only generates a new phase when no manifest exists; it reuses the existing manifest as-is when a manifest is published. Refuses to run if the private output directory exists to prevent overwriting or duplicate consumption.

Actual reproduction outputs should be saved separately and cannot replace already delivered test results; model services may produce different responses even with temperature set to 0. When exporting new results offline, be sure to use an independent checkout directory, as the exporter will write into this checkout. `results/metadata_supplement/`New results should retain their own source verification and result manifest.

## Anonymized export

```bash
python scripts/supplement/analyze.py runs/metadata_supplement/development runs/metadata_supplement/evaluation
python scripts/supplement/audit_calendar.py runs/metadata_supplement/evaluation
```

`analyze.py` Compare requests, responses, traces, tool executions, and pre- and post-simulation states, retain source SHA256, and export only metrics and verification.`audit_calendar.py` It is a post-hoc fact check added after discovering scoring issues and cannot serve as the primary metric for pre-registration.

Original conversations, requests, responses, simulated backend states, model weights, and keys are all retained in the ignored private directory.

This test encountered one interface timeout at entry 128 and subsequently ran only the 16 entries from the original list that had not started. To re-export this record, two directory segments must be provided simultaneously, see [continuation instructions](../../assignments/metadata_supplement/CONTINUATION_ZH.md). Cannot rerun the failed interface and then overwrite it with a successful result.
