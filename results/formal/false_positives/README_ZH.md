# False positives for legitimate declarations and legitimate calls

This inspection uses offline frozen detectors thresholds permissions and the original 20 official tasks. No new model requests were made and no strategy modifications or original experiment results were adjusted based on inspection results.

| Metrics | Numerator/Denominator | denominator meaning |
|---|---:|---|
| legitimate tool instruction mis-isolation | 1/24 | non-repeating original tool instruction |
| legitimate call mis-rejection at authorization layer | 0/31 | executable calls in upstream reference path |
| reference calls indicating isolation impact | 1/31 | same group of reference calls |
| reference calls fully blocked by gateway | 1/31 | Authorization denied or explanation quarantine union |

Original explanation of misquarantined: `get_current_day`. Rechecking the same explanation in the original task does not increase the count of independent text samples.

Legitimate call sources are fixed upstream reference solutions from AgentDojo versions, independent of this project’s permission rules. First verify the official initial state against existing permissions, then gradually read the reference path; only execute reference calls within the quarantined evaluation environment, record whether tool execution is effective, and check whether permissions were granted at that moment. Even if a call is rejected by policy, the reference environment still proceeds along the reference path, so this is a per-call compatibility diagnosis, not pretending the model bypasses rejection and continues execution.

A total of 31 reference calls, 0 unexecutable reference calls listed separately, not included in the denominator of legitimate calls.`checks.json` Provide for each task, tool, parameter hash, rejection reason, and source code hash of the reference; during reproducibility, read the reference solution again from fixed dependencies without exposing the full workspace state.

The reference solution is used only by this evaluator after official freezing, not for generating permissions, modifying prompts, or sending to the model. This false rejection rate only describes the reference path; it is not the overall false positive rate obtained by manually labeling every actual model proposal, nor can it be inferred that all valid expressions are allowed from zero false rejections. Total rejections in normal model tasks are documented elsewhere. [Overhead and false positive statistics](../overhead/README_ZH.md).

Running on compute node `python scripts/formal/check_false_positives.py --output runs/false-positive-check` Can be recomputed, requires configuration `TRUSTGATE_DETECTOR_DIR`. The main result retains a fixed version, and detector loading and inference are executed on CPU.
