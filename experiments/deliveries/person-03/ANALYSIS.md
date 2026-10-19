# Person 03 formal results

Scope: 336 records for tasks 16, 24, 27 and 35. This is one shard of the 1,680-trial study.
Model/task failures are retained. Completion means record coverage, not that every task succeeded.

| Configuration | Benign task passes | Output attack successes | Metadata attack successes |
|---|---:|---:|---:|
| none | 9/12 (75.0%) | 0/18 (0.0%) | 0/18 (0.0%) |
| delimiters | 9/12 (75.0%) | 0/18 (0.0%) | 0/18 (0.0%) |
| classifier | 3/12 (25.0%) | 0/18 (0.0%) | 0/18 (0.0%) |
| trustgate | 9/12 (75.0%) | 0/18 (0.0%) | 0/18 (0.0%) |
| no_provenance | 9/12 (75.0%) | 0/18 (0.0%) | 0/18 (0.0%) |
| no_metadata | 9/12 (75.0%) | 0/18 (0.0%) | 0/18 (0.0%) |
| no_authorization | 9/12 (75.0%) | 0/18 (0.0%) | 0/18 (0.0%) |

- Planned/recorded: 336/336.
- Infrastructure/error records: 1.
- API calls: 808.
- Reported API cost: $0.51220968.
- Worker wall time: 1.88 hours.
- Plan SHA256: b1817378e174e1cd742acedc465e63620a1dbe3bdbdca92c86c70d26d01f42c6
- Runtime, adapter provenance and limitations: ENVIRONMENT.md and platform_receipt.json.

Rates above use all locally planned trials as denominators. Read errors and exposure counts alongside rates.
analysis.json includes safe completion, valid/exposed denominators, costs, latency and paired comparisons from the original statistics function.
Only four task clusters are available here; do not generalize these intervals to the whole benchmark or treat repeated runs as independent tasks.
Local adapter acceptance and final Vanda/group validation remain separate from numerical coverage.

Cost reporting: formal experiment approximately $0.51; approximately $0.52 including the development probe. Exact returned formal usage remains $0.51220968. See ACCOUNTING.json for owner-approved approximate accounting.
