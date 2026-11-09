TrustGate report analysis attachment

Run from the extracted report source with Python 3.10 or later:
  python report_analysis.py --release /absolute/path/to/TrustGate --output /absolute/path/to/report-checks

The release directory must contain the unmodified TrustGate v1.0.1 files.
Choose an output directory outside that release. The script uses only the
Python standard library and makes no network or model requests.

Inputs
- assignments/formal/plan.json: expected trial identities and coverage.
- experiments/deliveries/person-01 through person-05/results.csv: 1,680 records.
- data/formal/attacks.json: template, goal and server-boundary classifications.
- results/formal/analysis/tables/main_metrics.csv: published count cross-check.

Outputs (included in report_checks/)
- main_counts.csv: the 21 surface/condition cells; the main-results table and its detailed Appendix C counterpart.
- exact_sign_flip_tests.csv: Appendix C exact tests; task-weighted differences,
  informative task counts and exact two-sided p-values.
- baselines_vs_none.csv: exploratory defense-minus-none comparisons and
  matched attack outcomes (both, none only, defense only).
- sensitivity_vanda_only.csv: 12-task Vanda-only attack-success comparison.
- resources_by_condition.csv: mean recorded runtime components, all 240 records
  per condition, including the one timeout.
- attack_exposure.csv: injection-point exposure, model exposure and filtering.
- gateway_activity_output.csv: authorization denials and denial-limit stops.
- attack_by_group.csv: Appendix C counts by template, goal and server boundary.
- classifier_by_template.csv: exposed payloads, filtered payloads and successes.
- benign_failure_modes.csv: mutually exclusive categories, in this priority:
  non-completion; authorization denial; tool error; native-check failure.
- status_counts.csv: end statuses of all 1,680 records.
- check_receipt.json: input SHA-256 hashes, coverage and primary-count checks.

Methods
Infrastructure-error records are excluded from outcome-rate comparisons, with
no success credit. Records are paired by task, slot and repeat; paired differences
are averaged within each task, then tasks receive equal weight. Exact sign-flip
tests use rational arithmetic and enumerate all signs on nonzero differences;
zero differences only repeat those outcomes and leave the exact p-value unchanged.

The primary report intervals retain the release's published paired_comparisons.csv
and paired_resources.csv. The two additional analyses (baselines versus none,
Vanda-only sensitivity) use 2,000 task resamples, random.Random(4213) reset for
each comparison, lexicographically sorted task IDs, and sorted-sample entries
50 and 1949 (zero-based). This explicit implementation fixes the resampling
order; its supplementary intervals are printed in the revised report. It does
not regenerate or overwrite the release's primary intervals.

This attachment supports report-specific summaries. The full release integrity
verifier, runtime checks and recorded demos remain the separate procedures in
Appendix A. The original measurements and native scores are unchanged.
