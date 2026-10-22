# Local and MCP final adaptation validation

This batch is executed separately after formal research to validate transmission adaptation, not included in original 1,680 results, no model, attack, threshold, or permission calls.

- Normal task: Original official tasks 0, 17, 27, 12, 31, 18 covering six business categories. Only unsecured configurations used to isolate transmission differences; three local/MCP runs each, totaling 36 entries.
- Output attack: output-1 from original tasks 0 and 17, same payload, same initial state, three local/MCP runs each, totaling 12 entries.
- Total 48 entries, 24 pairs, executed in adjacent pairs with randomized within-pair order and pair order (seed 421322). Each entry capped at eight requests, 180-second soft limit, 60-second per-request wait; maximum 384 requests, total reserved budget 1 USD.
- Original official executor and inventory unchanged. Additional native transport adapter appended after first successful read, same payload; MCP reuses existing server-side injection. Tools, calls, results, and states verified via eight deterministic dual-transport checks before paid trials.
- Retain all planned results. Stop the batch on infrastructure errors; do not rerun failed trials to replace their scores. Any continuation must separately list IDs that have not started.
- Report effective samples per entry, native task success, attack success, exposure, and duration. Samples small and reuse official tasks; this batch cannot prove statistical equivalence between two entries, nor serve as new attack generalization test.
- Maintain isolation; public metrics and source file hashes disclosed, private requests, responses, and full simulation states retained in runs/.

Generate plan.json once before run, freeze this file, executor, and 48 cases. Public reproducibility reuses this list; tasks cannot be reselected.
