# Published experiment datasets

All five shards are complete: **336 records each, 1,680 distinct trial IDs in total**. The source CSVs, execution receipts, and original provenance documents are preserved byte for byte. Status text written at initial delivery is historical; current coverage and validation are established by the common dataset manifest and reproduction entry point.

| Shard | Trial data | Platform |
|---|---|---|
| 1 | [results.csv](person-01/results.csv) | Vanda |
| 2 | [results.csv](person-02/results.csv) | macOS |
| 3 | [results.csv](person-03/results.csv) | WSL |
| 4 | [results.csv](person-04/results.csv) | Vanda |
| 5 | [results.csv](person-05/results.csv) | Vanda |

The retained timeout, cache recovery, platform differences, and valid denominators are explained in the [main results](../../results/formal/README_ZH.md) and [overhead analysis](../../results/formal/overhead/README_ZH.md). Use [the reproduction guide](../../docs/REPRODUCE_ZH.md) to verify these datasets and rebuild the tables. New replications must use separate output directories.
