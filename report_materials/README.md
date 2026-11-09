# Report reproducibility attachments

These files supplement the TrustGate v1.0.1 experiment release at commit
`baaba3eb8c64e0ff69bac1733694d23528968a14`. They provide the evidence index and
report-specific analyses cited by the final report. They do not change the
frozen measurements or native scores.

- `report_analysis.py`: recomputes report-specific counts, exact tests,
  additional comparisons, failure categories and resource summaries.
- `evidence_index.csv`: 40 claim/case mappings to files and fields in v1.0.1.
- `ANALYSIS_README.txt`: inputs, outputs and statistical conventions.
- `report_checks/`: 11 CSV outputs and one JSON verification receipt.

## Run

Python 3.10 or later is sufficient; no additional packages, network access,
model credentials or model calls are needed. From the repository root:

```bash
python report_materials/report_analysis.py --release . --output ../trustgate-report-checks
```

The output directory must be outside the release checkout. The command reads
1,680 recorded formal trials, checks 1,679 valid trials and validates primary
counts against the published tables. See `ANALYSIS_README.txt` for details.
The checked-in `report_checks/` files can be compared with the newly generated
outputs without overwriting the release.

The repository's existing `scripts/reproduce.py`, pinned runtime instructions
and recorded demos remain the procedures for the original release analyses and
runtime checks. This supplement does not replace those procedures.
