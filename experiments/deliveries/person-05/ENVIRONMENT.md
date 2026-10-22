# Person 5 run environment

- Cluster: NUS Vanda (PBS), queue batch_cpu (auto-routed), running host CN-017, job ID 1465592.stdct-mgmt-02
- System: Red Hat Enterprise Linux 9.4; CPU node 72 cores, job uses only 2 cores, GPU not requested (select=1:ncpus=2:mem=8gb, scheduler actually allocated 13GB)
- Python 3.10.20 self-built Miniforge environment (/scratch/<user>/miniforge3, environment name dsa4213); torch==2.7.1+cu126 installed as per docs/REPRODUCE_ZH.md, others installed per requirements-runtime-constraints.txt, pip check shows no conflicts
- Key dependencies: agentdojo 0.1.35, mcp 1.26.0, transformers 4.53.3, torch 2.7.1+cu126 (see receipt.json in same directory, consistent with frozen list, verified at startup)
- Git commit: ac919b6fe569984eb822c70a47e2a1400468e2fd; branch experiment-5
- Manifest SHA: b1817378e174e1cd742acedc465e63620a1dbe3bdbdca92c86c70d26d01f42c6; run ID formal-v1-001; shard shard-04
- Detector: protectai/deberta-v3-base-prompt-injection-v2, revision 90c9989b1a342275dd0d1a95aad283c04e075671, downloaded directly with huggingface_hub to a private cache; file hashes were verified at startup.
- Launcher: scripts/platforms/vanda-tangjiayi/person-5.pbs, copied from scripts/formal/person-5.pbs with two changes: the Conda loader points to a personal Miniforge installation, and offline checks (unittest and scripts/formal/preflight.py) precede the formal run. No API calls start if these checks fail.
- Launch method (no key values): from the repository root, set TRUSTGATE_RUN_ID, TRUSTGATE_KEY_FILE (a private file with mode 600), and TRUSTGATE_DETECTOR_DIR, then `qsub -v TRUSTGATE_RUN_ID,TRUSTGATE_KEY_FILE,TRUSTGATE_DETECTOR_DIR scripts/platforms/vanda-tangjiayi/person-5.pbs`
- Additional checks before execution on CN-017 made no API calls: 33 unit tests, formal preflight, trustgate inspect, and formal_manifest.verify_runtime all passed.
- No .py files, configurations, or lists were modified
- Results: 336/336 records, with 336 unique case_id values matching shard-04 exactly; complete=true, fatal_error=null; approximately 9,343 seconds of wall time; API-reported cost $0.670 (budget $2; no budget stop).
- Status counts: completed 302 times and model_call_budget 34 times (the 8-call limit per trial); all records retained unchanged.
- Export: run on compute node CN-016 `python -m trustgate export`(job 1465907), generate this directory results.csv and receipt.json
