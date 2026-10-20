# Person 03 observed results (review only)

Each row has 12 benign, 18 output-attack and 18 metadata-attack planned trials. Attack success is an undesired outcome.

| Configuration | Benign task passes | Output attack successes | Metadata attack successes |
|---|---:|---:|---:|
| none | 9/12 | 0/18 | 0/18 |
| delimiters | 9/12 | 0/18 | 0/18 |
| classifier | 3/12 | 0/18 | 0/18 |
| trustgate | 9/12 | 0/18 | 0/18 |
| no_provenance | 9/12 | 0/18 | 0/18 |
| no_metadata | 9/12 | 0/18 | 0/18 |
| no_authorization | 9/12 | 0/18 | 0/18 |

One output/trustgate trial has a TimeoutError. Do not interpret this infrastructure error as successful defense.
Zero observed attacks under the undefended baseline limits evidence of additional defense benefit in this shard.
analysis.json preserves error/exposure denominators and task-cluster paired comparisons from the original statistics function.
Only four task clusters are present; this is not the whole study. No parameter or attack was changed using these test results.
Fees remain unresolved as disclosed above; this bundle is for review and is not final merge acceptance.
