# Person 02 delivery — local Mac, pending platform review

This delivery provides the original assigned 336 unique trial records and exact total API cost **$0.72108042**. All failures remain. There were 168 native task passes, 20 model-call-budget stops and two denial-budget stops; Python exception rows are zero.

## Data and pause recovery

- `results.csv`: canonical 336-row dataset, normalized to LF without changing field values.
- This delivery contains exactly one result CSV. Before-pause and after-resume partition backups remain private locally.
- `ACCOUNTING.json`: distinguishes logical row partitions from when API charges occurred. The recovered trial's five cached responses were paid before the pause and are included exactly once.
- `RECOVERY.json`: trial151 exact-request replay, preserved eight-call/time bounds and latency caveat. Original private attempt remains intact.

## Receipts and required review

`receipt.json` supplies standard measurement fields so the shared tooling can read the data. It explicitly records **actual Mac/CPU Torch 2.7.1, no PBS, pending team review**, plus adapter and continuation hashes. This is a newly generated truthful measurement receipt, not a renamed or falsified Vanda credential. The original `local-receipt.json` remains alongside it.

The existing summary collector checks plan/source identity but does not enforce platform approval. Its ability to read this receipt must not be interpreted as Vanda acceptance. Team review remains required before pooling or merging. Frozen source, payloads, permissions, task IDs, detector weights and model/provider are unchanged.

## Validation and limitations

Run `python tasks/02/prepare_delivery.py --check` for identity, partition, cost, hashes and privacy checks. Add `--require-platform-approved` to test the acceptance gate; it intentionally fails while team platform review is pending.

`AUDIT_REPORT.json` and `AUDIT_ZH.txt` preserve the observed false-positive classifier, native grading limitations, weak unprotected attack baseline and trial151 timing warning. Zero attack success in a cell does not establish general defense superiority.

Credentials, model weights, full dialogues, simulated email/file states and private logs are excluded. Nothing is uploaded automatically. PR review and main merge remain human actions.
