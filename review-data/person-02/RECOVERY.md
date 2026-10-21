# Experiment 2 interruption and exact cache continuation

Required selected case: `98f0051e9f3cdb5a5daf`, task32 / benign / none / repeat1, original trial151. This is the same observation already included once in the final 336 rows.

1. The user requested a pause after 150 completed rows. The old attempt of trial151 retained five paid model request/response pairs but no final summary. The old directory, claim and completed rows were retained.
2. A zero-paid-request offline replay checked exact equality of each entire outgoing request against its original cached request, and reused the corresponding paid response to reconstruct only simulated state. The passed replay report and old/new hashes are in [RECOVERY.json](RECOVERY.json). No repeated live requests were used for those five steps.
3. The continuation resumed live requests at logical step6, retaining the original eight-call limit. The recovered trial finished with six logical calls in total and native utility=true. Its cached cost was $0.00425460; the one new step cost $0.00128088; its final row cost is $0.00553548, counted once.
4. Total batch usage.cost is $0.72108042 across 1,338 unique paid response IDs. The five physical cache copies are excluded from duplicate billing. Original150 row cost $0.33796212 plus cached trial151 cost $0.00425460 explains the $0.34221672 charged before the pause. New charges after continuation are $0.37886370. Pending and uncertain reservations are zero.
5. Timing retains the reconstructed 37.0817391872406 seconds of prior trial elapsed time, leaving 142.9182608127594 seconds of its original 180-second limit. Historical API durations come from request/response filesystem timestamps. Pause time is excluded; this trial should be flagged/excluded in a timing sensitivity analysis. Combined worker wall time is the sum of two active worker periods, not an uninterrupted wall-clock interval.

These materials disclose execution provenance without changing any score or version fingerprint. Exact original request/response content and simulated state remain private; hashes are published for later private verification.
