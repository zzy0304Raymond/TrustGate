# for participants in experiment 2, 3, 4, and 5

**All four materials for this round have been collected and passed consistency review no further submission required.** The original export method is retained below for reproducibility final check results are available at [180 summaries](README_ZH.md).

This time only **one JSON check file** needs to be submitted no need to rerun the experiment no API usage and no uploading of raw requests complete states or keys.

1. Obtain the code version containing `scripts/formal/extract_metadata_trace_checks.py` retain the original experiment directory and use the original Python 3.10.20 dependency environment. Do not modify the frozen algorithm results or execution credentials.
2. Locate your original shard directory: it should contain `results.json` and subdirectories of each case; the case directory contains `summary.json`round by round `request_*.json` / `response_*.json`, `trajectory.json`, `tool_calls.json`, `defense_events.json`, `api_usage.json`, `raw_tools.json` and `environment_before.json` / `environment_after.json`Publicly available `results.csv` or excerpts cannot replace these original documents.
3. Execute the following command in the repository root directory. Replace the personnel ID, directory path, and output filename with your own; no manual selection of cases is required as the script will verify your 36 items `none` / `trustgate` Tool instruction attack.

Vanda: First log in to the PBS computing node and activate `dsa4213`For example: Experiment 4

```bash
python scripts/formal/extract_metadata_trace_checks.py \
  --person 4 \
  --shard-dir /actual path/original shard directory \
  --output results/formal/metadata_diagnosis/trace_checks_person-04.json
```

Mac / WSL: Use the same script in your original environment with additional `--platform local`. Taking Experiment 2 as an example:

```bash
python scripts/formal/extract_metadata_trace_checks.py \
  --platform local --person 2 \
  --shard-dir /actual path/original shard directory \
  --output results/formal/metadata_diagnosis/trace_checks_person-02.json
```

Other clusters must run on the compute nodes assigned by this platform;`--platform local` Only disable Vanda’s PBS check without exempting platform scheduling rules. If the original directory structure differs, adapt path reading accordingly without modifying the original files or bypassing checks through forged environment variables.

| Experiment | Personnel parameters | The only file required for submission |
|---|---|---|
| 2 | `--person 2` | `trace_checks_person-02.json` |
| 3 | `--person 3` | `trace_checks_person-03.json` |
| 4 | `--person 4` | `trace_checks_person-04.json` |
| 5 | `--person 5` | `trace_checks_person-05.json` |

The script will output after successful execution `passed: true`, `cases: 36` and `new_model_requests: 0`Submit the corresponding JSON to `results/formal/metadata_diagnosis/`create a PR in your own branch. If an error occurs, retain the error message and original file. Let the consolidator identify the cause. Do not manually modify check results, fabricate missing records, or repeatedly invoke the model.

The script has been validated on the Vanda original from Experiment 1. Actual originals on other platforms still require validation via the same fields, status, and source code; checks that have not been delivered cannot be pre-marked as completed.
