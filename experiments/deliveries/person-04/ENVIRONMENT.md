# Participant 4 runtime environment

- Cluster: NUS Vanda (PBS) running on host CN-016 job ID 1462590.stdct-mgmt-02
- System: Red Hat Enterprise Linux 9.4 CPU: Intel Xeon Platinum 8452Y only CPU used no GPU requested (select=1:ncpus=2:mem=8gb)
- Python 3.10.20 self-built Miniforge environment (/scratch/<user>/miniforge3 environment name dsa4213) installed according to requirements-runtime-constraints.txt
- Key dependencies: see packages field in receipt.json in the same directory (consistent with frozen list verified at startup)
- Git commit: a37fc06258e80ffb0d63298e1fab0c11b4065dca branch experiment-4
- List SHA: b1817378e174e1cd742acedc465e63620a1dbe3bdbdca92c86c70d26d01f42c6; Run ID: formal-v1-001; Shard: shard-03
- Detector: protectai/deberta-v3-base-prompt-injection-v2, revision 90c9989b1a342275dd0d1a95aad283c04e075671, downloaded directly via huggingface_hub, file hash verified at startup
- Startup script: scripts/platforms/vanda-jingfangxue/person-4.pbs, copied from scripts/formal/person-4.pbs, with two changes: conda loading path changed to self-built Miniforge; offline check (unittest and scripts/formal/preflight.py) added before formal execution, preventing API calls if check fails
- No .py files, configurations, or lists were modified
- Results: 336/336 records, complete=true, fatal_error=null; wall clock time approximately 7,213 seconds; API reported cost $0.455
