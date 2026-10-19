# Actual person-03 runtime and acceptance status

- Platform: WSL2 / Ubuntu 22.04.5; CPU only; no GPU used by the experiment.
- Python: 3.10.20
- Kernel: 6.6.87.2-microsoft-standard-WSL2
- Frozen plan SHA256: b1817378e174e1cd742acedc465e63620a1dbe3bdbdca92c86c70d26d01f42c6
- Frozen model/provider: qwen/qwen3-30b-a3b-instruct-2507 / SiliconFlow; temperature=0.
- Packages: {"agentdojo": "0.1.35", "mcp": "1.26.0", "openai": "3.31.0", "pydantic": "2.14.1", "torch": "2.7.1+cu126", "transformers": "4.53.3"}
- Detector files: SHA256 pins verified; actual hashes are in review_receipt.json.
- Hardware: {"cpu_model": "Intel(R) Core(TM) i9-14900HX", "logical_cpus": 32, "memory_total": "7985272 kB"}
- Random seed/thread environment: {"MKL_NUM_THREADS": "2", "OMP_NUM_THREADS": "2", "PYTHONHASHSEED": "0", "TOKENIZERS_PARALLELISM": "false"}
- Original 25 frozen Python files and original executable plan unchanged. Seven extra local adapter hashes are recorded separately.
- Entry points: scripts/platforms/local/run.py, then tasks/03/resume.py; all attempt boundaries and entrypoint hashes are preserved.
- Historical pause/resume: initial 18 records; first recovery to 58 with one timeout; second recovery to 191, safe user pause; final recovery to 336. No case was retried.
- Cost: reported $0.51220968; uncertain reservation $0.05; pending request reservation $0. No running experiment or MCP process remains.
- Timing: 6750.4345 seconds is the sum of case seconds across attempts, excluding startup, export and user pauses. It is not uninterrupted worker wall time.
- Verification: real WSL offline unit tests, 116 dependency pins, 60 attack transport checks, 34 scripted loops and real CPU detector smoke checks.
- Collection complete=true; cost_reconciled=false; final_delivery_ready=false; Vanda/team acceptance not performed.
- Group 9 credentials, group CSV, original requests/responses, model weights and simulated backend state remain private.
