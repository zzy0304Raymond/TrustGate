# Person 02 execution environment

- Run ID: `local-person2-20261019-001`
- Person: 2; shard index: 1
- Platform: Darwin arm64; OS release 25.4.0
- Scheduler: none (local process); detector on CPU, two threads; GPU unused
- Python: 3.10.20
- Upstream commit: `30ff95593fa27ee117991ef0da5d71d3eb5294d5`
- Upstream plan SHA256: `b1817378e174e1cd742acedc465e63620a1dbe3bdbdca92c86c70d26d01f42c6`
- Local execution SHA256: `9f035b8069725c351b9aea376569252c5b484f32bfce5dd03b544a58b156d65b`
- Model: qwen/qwen3-30b-a3b-instruct-2507; provider: SiliconFlow; temperature 0
- Scope: original person-02 336 trials, original ordering and case IDs
- API stop budget: USD 2; request reservation USD 0.05; no automatic retries
- Startup: `bash scripts/platforms/local/person2.sh run --run-id local-person2-20261019-001`
- Offline checks: 37 tests; 24 MCP tools; 60 attack transport checks; pinned detector hashes verified
- Platform difference: native torch 2.7.1 in place of 2.7.1+cu126. Frozen upstream execution code is unchanged; the local adapter starts identical MCP services without PBS.
- Vanda equivalence and team acceptance: unverified, requires review before pooling results

## Key package versions

- agentdojo: `0.1.35`
- mcp: `1.26.0`
- transformers: `4.53.3`
- torch: `2.7.1`
- pydantic: `2.14.1`
- openai: `3.31.0`

## Explicit continuation after user pause

- Continuation run: `local-person2-20261019-001-resume01`
- Continuation manifest: `34df12830603ca06b8e0bd56bd79bccb7c58711db84c929d58cc28ac3527a5a6`
- Original 150 records retained unchanged. Trial 151 restores its first five paid responses only after exact request comparison in a no-API replay. Subsequent calls retain the original 8-call budget.
- Total USD 2 cap includes prior USD 0.34221672. Cached responses are not billed twice.
- Trial 151 latency includes pre-pause active time; old API durations use file timestamps and must be flagged in statistical latency comparisons. Pause duration is excluded.

## Submission-format receipt

`receipt.json` is generated from the verified completed measurements with actual Mac package versions and an explicit pending-team-review acceptance block. `local-receipt.json` is preserved unchanged. Standard parser compatibility does not certify Vanda equivalence.
