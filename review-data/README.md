# Experimental review materials

This directory is used to centrally collect de-identified review records for formal experiments. Existing formal scores remain unchanged, and review findings are recorded separately from original scores.

The first round list contains 52 records covering 11 tasks; all 52 have completed review, conclusions see[Unified analysis and per-item classification](../results/formal/review/README_ZH.md). This list consists of cases selected for specific issues and is not used to re-estimate overall success rate or false positive rate.

## Submit experiment

| Experiment | task | Number of verified records | Sampling checklist |
|---|---|---:|---|
| Experiment 1 | 31 | 9 | [person-01/selection.csv](person-01/selection.csv) |
| Experiment 2 | 2, 32 | 12 | [person-02/selection.csv](person-02/selection.csv) |
| Experiment 3 | 16, 24 | 10 | [person-03/selection.csv](person-03/selection.csv) |
| Experiment 4 | 3, 18 | 8 | [person-04/selection.csv](person-04/selection.csv) |
| Experiment 5 | 5, 9, 30, 33 | 13 | [person-05/selection.csv](person-05/selection.csv) |

Each checklist provides `case_id`task, scenario, attack slot, configuration, repetition number, and verification purpose. Locate the corresponding record using the exact number; do not rerun experiments to replace original records.

Each record is placed under the individual’s directory, named `case_id` for example:

```text
review-data/
  person-02/
    selection.csv
    <case_id>/
      evidence.json
      explanation.md
```

The filename can reuse the existing format within the group. The verification materials should explain:

- Task requirements and actual operations performed.
- Tool invocation sequence, required parameters, and success or error status of the tools.
- Decisions and justifications for allowing, rejecting, or hiding tools under protection.
- Scoring criteria, original scores, and corresponding evidence.
- Reason for stopping; if timeout or recovery is involved, include relevant time and cost explanations.
- Original filename, SHA-256, and which content has been de-identified or omitted in the excerpt.

Original complete requests responses and backend status are retained in their respective private execution directories. This directory submits de-identified excerpts and analysis suitable for public release; full status verification requires separate private transfer. De-identified copies cannot directly replace original status for re-scoring, and content cannot be altered to change original results.

## Two special records

- Experiment 2: Task 32,`benign`, `none`, repetition 1,`case_id=98f0051e9f3cdb5a5daf`, corresponding to original trial151. Verification materials should explain the original interruption attempt, cache recovery, timing, and cost methodology; this record is already included in the 12-item list.
- Experiment 3: Task 24,`output-2`, `trustgate`, repetition 1,`case_id=9f7467fd5e9ede0aa172`, is the only one `TimeoutError`. Retain explanation of errors and requested costs; this record and the unprotected control are already included in the 10-item list.

## Public access scope

The current repository is publicly visible. Do not submit API keys, authentication headers, `.env`, `.secrets`group keys CSV, model weights, real personal information, or sensitive business content.

Subsequent deletion of this directory will not automatically remove files from Git history; materials should be suitable for public release from the first commit onward. After verification conclusions are compiled into the official result statement, this collection directory may be removed.
