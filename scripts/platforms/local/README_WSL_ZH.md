# WSL / Linux run source

Shard 3 ran on WSL2 / Ubuntu 22.04.5 with Python 3.10.20. It contains 336 records, including one retained TimeoutError. Data, environment, and recovery evidence are in [person-03](../../../experiments/deliveries/person-03/README.md), combined statistics and error denominator see [formal results](../../../results/formal/README_ZH.md).

This directory inherits the frozen state `FormalExperiment`Independently adapts to MCP process startup and local scheduling without forging PBS job IDs. Core source code, models, permissions, and attack lists remain frozen; actual adapter hashes are preserved with delivery.`tasks/03/resume.py`Early recovery versions and verification scripts are retained in the original path for source verification.

## Environment and offline inspection

According to [Unified reproduction instructions](../../../docs/REPRODUCE_ZH.md) Install Python 3.10.20 and fixed dependencies. Official adaptation for Linux/WSL uses Torch 2.7.1+cu126 and runs on CPU.

```bash
export PYTHONHASHSEED=0 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TRUSTGATE_DETECTOR_DIR="$PWD/models/prompt_injection_detector"
python scripts/platforms/local/prepare_detector.py --detector-dir "$TRUSTGATE_DETECTOR_DIR"
python scripts/platforms/local/run.py --check --detector-dir "$TRUSTGATE_DETECTOR_DIR"
python scripts/platforms/local/offline.py --detector-dir "$TRUSTGATE_DETECTOR_DIR"
```

These native entries will be rejected in real PBS jobs; Vanda should use the public PBS entry. Offline inspection uses preset responses and does not count toward model performance experiments.

## Reproduce this real model experiment

The native entry only handles the original Part 3; use the new checkout directory, new run ID, and private credential file while preserving published data.

```bash
export TRUSTGATE_KEY_FILE=/absolute/private/openrouter_group9.key
python scripts/platforms/local/run.py --execute \
  --detector-dir "$TRUSTGATE_DETECTOR_DIR" --run-id replication-person3-001
python scripts/platforms/local/delivery.py export \
  --worker-dir runs/studies/replication-person3-001/shard-02 \
  --destination runs/export-person03
```

Record rejections, timeouts, and call limits. Export with the same metrics and native source credentials; do not disclose keys, requests, or simulated states. Cross-platform statistics from original results are verified via unified entry, but native run speed cannot be directly interpreted as a hardware comparison with Vanda.
