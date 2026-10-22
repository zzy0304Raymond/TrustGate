# Run interruption and remaining list

The original assessment list had 144 items. Item 128 (`11df1052bb099ae64ee7`task 23, delimiter, call example template, repeat 2) encountered a 60-second read timeout during the third model request, and the original batch was stopped according to the rules. This record was retained as an interface error, not rerun or replaced, and was not counted as a valid attack failure.

[Continuation list](continuation-01.json) contains only items 129–144 in the original order, all previously unstarted. It records the original results, original execution summary, parent manifest, and continuation script hash to prevent duplicate runs or overwriting existing data. Its $1 budget is taken from the remaining allowance of the original $3 evaluation budget; the timed-out request retains its $0.05 reservation, so the total stopping budget is unchanged.

Development and original assessment executor `study.py` Remains frozen.`continue_remaining.py` Reuse exactly the same `FormalExperiment`models, tools, thresholds, scores, and the maximum number of calls per case are handled, responsible only for explicitly defined remaining case loops and independent budget ledgers. It does not provide automatic retries.

The summary retains all 144 planned IDs, including 143 valid comparisons and 1 infrastructure failure. Model-call budget exhaustion remains a valid task failure and stays in the comparison; the interface timeout is listed separately. Original partial scores are retained as observations of state and handled through `valid_for_comparison` to prevent counting interface errors as successful defenses. All 18 pairs of unprotected/TrustGate are fully valid.

This private record is divided into `evaluation/` and `continuation-01/` segments; when re-exporting, both must be provided simultaneously:

```bash
python scripts/supplement/analyze.py runs/metadata_supplement/development runs/metadata_supplement/evaluation --continuation runs/metadata_supplement/continuation-01
python scripts/supplement/audit_calendar.py runs/metadata_supplement/evaluation --continuation runs/metadata_supplement/continuation-01
```
