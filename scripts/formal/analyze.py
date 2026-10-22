"""Create reproducible tables and figures from the five frozen public deliveries."""
import sys as _release_sys
from pathlib import Path as _ReleasePath
_release_sys.path.insert(0, str(_ReleasePath(__file__).resolve().parents[2]))
from release_integrity import recorded_digest
import argparse
from collections import Counter
import csv
from decimal import Decimal
import hashlib
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from trustgate.planning import CONDITIONS, read_plan
from trustgate.runner import require_compute

SURFACES = ("benign", "output", "metadata")
LABELS = {
    "none": "No defense", "delimiters": "Prompt defense",
    "classifier": "Classifier", "trustgate": "TrustGate",
    "no_provenance": "Without provenance", "no_metadata": "Without screening",
    "no_authorization": "Without authorization",
}
ZH_LABELS = {
    "none": "No defense", "delimiters": "Prompt protection", "classifier": "Classifier",
    "trustgate": "Full TrustGate", "no_provenance": "remove source attribution",
    "no_metadata": "Remove indication screening", "no_authorization": "remove execution authorization",
}
NUMERIC = {
    "repeat", "seconds", "api_calls", "api_seconds", "cost_usd", "prompt_tokens",
    "completion_tokens", "tool_calls", "tool_errors", "authorization_blocks",
    "authorization_checks", "metadata_quarantines", "metadata_examined",
    "benign_metadata_quarantines", "benign_metadata_examined", "detector_seconds",
    "cross_server_write_calls",
}
IDENTITY = (
    "task", "slot_id", "attack_case_id", "split", "workflow", "surface",
    "condition", "repeat", "transport",
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return recorded_digest(hashlib.sha256(path.read_bytes()).hexdigest())


def original_summary_module():
    spec = importlib.util.spec_from_file_location("formal_summary", ROOT / "scripts/formal/summarize.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_deliveries(root, plan, manifest):
    """Require complete, unchanged public data before producing any statistics."""
    if manifest["plan_sha256"] != plan["plan_sha256"]:
        raise ValueError("Dataset manifest belongs to another plan")
    expected = {case["case_id"]: case for shard in plan["shards"] for case in shard["cases"]}
    rows, seen, input_hashes = [], set(), {}
    for person in range(1, 6):
        folder = root / f"experiments/deliveries/person-{person:02d}"
        entries = [s for s in manifest["shards"] if s["person"] == person]
        if len(entries) != 1:
            raise ValueError("Each delivery must have exactly one dataset manifest entry")
        hashes = {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob("*")) if p.is_file()}
        if hashes != entries[0]["delivery_sha256"]:
            raise ValueError(f"Person {person}: delivery files differ from the published manifest")
        input_hashes[f"person-{person:02d}/results.csv"] = hashes["results.csv"]
        receipt = load(folder / "receipt.json")
        if (receipt["person"] != person or receipt["shard_index"] != person - 1
                or receipt["plan_sha256"] != plan["plan_sha256"]
                or receipt["source_sha256"] != plan["source_sha256"]):
            raise ValueError("Receipt identity mismatch")
        with (folder / "results.csv").open(newline="", encoding="utf-8") as stream:
            records = list(csv.DictReader(stream))
        if [r["case_id"] for r in records] != [c["case_id"] for c in plan["shards"][person - 1]["cases"]]:
            raise ValueError("Delivery order or case coverage differs from the frozen shard")
        for raw in records:
            case_id = raw["case_id"]
            if case_id in seen or case_id not in expected:
                raise ValueError("Duplicate or foreign case")
            seen.add(case_id)
            case = expected[case_id]
            if any(raw[k] != ("" if case.get(k) is None else str(case[k])) for k in IDENTITY):
                raise ValueError("Trial identity changed")
            row = {}
            for key, value in raw.items():
                if value in ("True", "False"):
                    row[key] = value == "True"
                elif value == "":
                    row[key] = None
                elif key in NUMERIC:
                    row[key] = float(value)
                    if not math.isfinite(row[key]) or row[key] < 0:
                        raise ValueError("Invalid measurement")
                else:
                    row[key] = value
            row["repeat"] = int(row["repeat"])
            row["_cost_decimal"] = Decimal(raw["cost_usd"])
            row["person"] = person
            row["platform"] = entries[0]["execution_platform"]
            if not row["error_type"]:
                if not isinstance(row["native_utility"], bool):
                    raise ValueError("Valid trial has no task outcome")
                if row["surface"] != "benign":
                    if not isinstance(row["attacker_success"], bool):
                        raise ValueError("Valid attack trial has no attack outcome")
                    if row["safe_completion"] is not (row["native_utility"] and not row["attacker_success"]):
                        raise ValueError("Safe completion is inconsistent with recorded outcomes")
            rows.append(row)
    if seen != set(expected) or len(rows) != plan["planned_cases"]:
        raise ValueError("Formal data are incomplete")
    return rows, input_hashes


def fraction(n, d):
    return n / d if d else None


def aggregate(rows, planned, attack):
    """Errors remain in planned denominators and are never credited as successes."""
    valid = [r for r in rows if not r.get("error_type") and not r.get("error")]
    task_passes = sum(r["native_utility"] is True for r in valid)
    attack_successes = sum(r["attacker_success"] is True for r in valid) if attack else None
    safe = sum(r["safe_completion"] is True for r in valid) if attack else None
    exposed = [r for r in valid if r["injection_reached_model"] is True] if attack else []
    cost = sum((r["_cost_decimal"] for r in rows), Decimal(0))
    return {
        "planned": planned, "recorded": len(rows), "valid": len(valid),
        "missing": planned - len(rows), "errors": len(rows) - len(valid),
        "task_passes": task_passes, "task_success_per_planned": fraction(task_passes, planned),
        "task_success_per_valid": fraction(task_passes, len(valid)),
        "attack_successes": attack_successes,
        "attack_success_per_planned": fraction(attack_successes, planned) if attack else None,
        "attack_success_per_valid": fraction(attack_successes, len(valid)) if attack else None,
        "safe_completions": safe, "safe_completion_per_planned": fraction(safe, planned) if attack else None,
        "safe_completion_per_valid": fraction(safe, len(valid)) if attack else None,
        "exposed_valid": len(exposed) if attack else None,
        "attack_success_given_exposure": fraction(sum(r["attacker_success"] is True for r in exposed), len(exposed)) if attack else None,
        "model_calls": sum(int(r["api_calls"]) for r in rows),
        "prompt_tokens": sum(int(r["prompt_tokens"]) for r in rows),
        "completion_tokens": sum(int(r["completion_tokens"]) for r in rows),
        "reported_cost_usd": format(cost, ".8f"),
        "legitimate_metadata_quarantines": sum(int(r["benign_metadata_quarantines"] or 0) for r in rows),
        "legitimate_metadata_examined": sum(int(r["benign_metadata_examined"] or 0) for r in rows),
        "benign_authorization_denials_proxy": sum(int(r["authorization_blocks"] or 0) for r in rows) if not attack else None,
    }


def build_tables(plan, rows, summary):
    cases = [c for s in plan["shards"] for c in s["cases"]]
    cells = []
    for surface in SURFACES:
        for condition in CONDITIONS:
            selected = [r for r in rows if (r["surface"], r["condition"]) == (surface, condition)]
            planned = sum((c["surface"], c["condition"]) == (surface, condition) for c in cases)
            cells.append(dict(surface=surface, condition=condition, **aggregate(selected, planned, surface != "benign")))
    task_cells = []
    for task in sorted({r["task"] for r in rows}, key=lambda x: int(x.rsplit("_", 1)[1])):
        for surface in SURFACES:
            for condition in CONDITIONS:
                selected = [r for r in rows if (r["task"], r["surface"], r["condition"]) == (task, surface, condition)]
                planned = sum((c["task"], c["surface"], c["condition"]) == (task, surface, condition) for c in cases)
                if planned:
                    task_cells.append(dict(task=task, workflow=selected[0]["workflow"],
                        person=selected[0]["person"], platform=selected[0]["platform"],
                        surface=surface, condition=condition,
                        **aggregate(selected, planned, surface != "benign")))
    paired = []
    for item in summary["paired_comparisons"]:
        low, high = item["task_cluster_bootstrap_95_ci"]
        paired.append({
            "surface": item["surface"], "metric": item["metric"],
            "reference": item["comparison"].removeprefix("trustgate minus "),
            "paired_tasks": item["paired_tasks"], "paired_observations": item["paired_observations"],
            "difference_pp": item["task_weighted_difference"] * 100,
            "ci_low_pp": low * 100, "ci_high_pp": high * 100,
            "interval_includes_zero": low <= 0 <= high,
            "degenerate_bootstrap_interval": low == high,
            "multiple_comparison_adjustment": "none",
        })
    resources = []
    for condition in CONDITIONS:
        selected = [r for r in rows if r["condition"] == condition]
        cost = sum((r["_cost_decimal"] for r in selected), Decimal(0))
        resources.append({
            "condition": condition, "recorded": len(selected),
            "errors": sum(bool(r["error_type"]) for r in selected),
            "reported_cost_usd": format(cost, ".8f"),
            "mean_reported_cost_usd": float(cost) / len(selected),
            "mean_model_calls": statistics.mean(r["api_calls"] for r in selected),
            "mean_prompt_tokens": statistics.mean(r["prompt_tokens"] for r in selected),
            "mean_completion_tokens": statistics.mean(r["completion_tokens"] for r in selected),
            "mean_total_tokens": statistics.mean(r["prompt_tokens"] + r["completion_tokens"] for r in selected),
        })
    statuses = [dict(person=person, status=status, records=count)
                for person in range(1, 6)
                for status, count in sorted(Counter(r["status"] for r in rows if r["person"] == person).items())]
    return {"main_metrics": cells, "paired_comparisons": paired, "task_metrics": task_cells,
            "resource_summary": resources, "status_counts": statuses}


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def make_figures(tables, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.ticker import PercentFormatter

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.titleweight": "bold", "axes.labelcolor": "#293548",
        "text.color": "#17243a", "axes.edgecolor": "#c3cbd5",
        "grid.color": "#dce2ea", "pdf.fonttype": 42, "ps.fonttype": 42})
    colors = ["#8391a5", "#b19b78", "#aa6f70", "#167b8c", "#729f9e", "#83a6bd", "#c1995b"]
    cells = {(r["surface"], r["condition"]): r for r in tables["main_metrics"]}
    labels = [LABELS[c] for c in CONDITIONS]
    figure_dir = output / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    produced = []

    def finish(fig, name, note):
        fig.text(.02, .025, note, fontsize=8, color="#526174", va="bottom")
        fig.tight_layout(rect=(0, .10, 1, .94))
        for suffix in ("png", "pdf"):
            path = figure_dir / f"{name}.{suffix}"
            fig.savefig(path, dpi=180, facecolor="white", metadata={"Creator": "TrustGate", "CreationDate": None} if suffix == "pdf" else {"Software": "TrustGate"})
        plt.close(fig)
        produced.append(name)

    def horizontal(ax, surface, numerator, denominator, title, maximum=100):
        values = [100 * cells[surface, c][numerator] / cells[surface, c][denominator] for c in CONDITIONS]
        ax.barh(range(7), values, color=colors, height=.64)
        for i, c in enumerate(CONDITIONS):
            row = cells[surface, c]
            suffix = "*" if row["errors"] else ""
            ax.text(values[i] + maximum * .018, i, f'{row[numerator]}/{row[denominator]}{suffix}',
                    va="center", fontsize=9)
        ax.set(yticks=range(7), yticklabels=labels, xlim=(0, maximum), title=title)
        ax.invert_yaxis()
        ax.xaxis.set_major_formatter(PercentFormatter(100))
        ax.xaxis.grid(True, alpha=.5)
        ax.set_axisbelow(True)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    horizontal(axes[0], "benign", "task_passes", "planned", "Benign task completion")
    horizontal(axes[1], "output", "attack_successes", "valid", "Output attack success", 20)
    horizontal(axes[2], "metadata", "attack_successes", "valid", "Metadata attack success", 20)
    fig.suptitle("Formal results | Security and benign utility", fontsize=16, x=.02, ha="left")
    finish(fig, "01_security_and_utility",
        "Counts are shown on every bar. *TrustGate output: 89 valid trials + 1 timeout out of 90 planned.\n"
        "Zero observed metadata successes in every condition provide no estimate of comparative security benefit.")

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6))
    horizontal(axes[0], "output", "safe_completions", "planned", "Output attacks")
    horizontal(axes[1], "metadata", "safe_completions", "planned", "Metadata attacks")
    fig.suptitle("Safe completion | User task passed and attacker objective failed", fontsize=15, x=.02, ha="left")
    finish(fig, "02_safe_completion",
        "Denominator: all 90 planned trials per condition and surface. *The timeout is retained and receives no success credit.\n"
        "State-based success does not establish that the final answer is semantically unaffected.")

    def forest(ax, surface, metric, references, title):
        records = [next(r for r in tables["paired_comparisons"]
                        if (r["surface"], r["metric"], r["reference"]) == (surface, metric, ref)) for ref in references]
        for i, row in enumerate(records):
            color = "#167b8c" if not row["degenerate_bootstrap_interval"] else "#8391a5"
            ax.hlines(i, row["ci_low_pp"], row["ci_high_pp"], color=color, lw=2.5)
            ax.plot(row["difference_pp"], i, "D" if row["degenerate_bootstrap_interval"] else "o",
                    color=color, markerfacecolor="white" if row["degenerate_bootstrap_interval"] else color)
        ax.axvline(0, color="#6d7785", ls="--", lw=1)
        ax.set(yticks=range(len(references)), yticklabels=[LABELS[r] for r in references],
               title=title, xlabel="TrustGate minus comparator (percentage points)")
        ax.set_ylim(len(references) - .6, -.6)
        ax.xaxis.grid(True, alpha=.5)
        ax.set_axisbelow(True)
        return records

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4))
    refs = ("none", "delimiters", "classifier")
    forest(axes[0], "benign", "native_utility", refs, "Benign completion | higher is better")
    forest(axes[1], "output", "attacker_success", refs, "Output attack success | lower is better")
    forest(axes[2], "output", "safe_completion", refs, "Output safe completion | higher is better")
    fig.suptitle("Paired comparisons | Task-weighted differences", fontsize=16, x=.02, ha="left")
    finish(fig, "03_paired_comparisons",
        "Pointwise 95% task-cluster bootstrap intervals, 2,000 resamples, 20 tasks; no multiple-comparison correction.\n"
        "Differences average paired observations within each task, then weight tasks equally; they can differ from pooled-rate differences.")

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 7.8))
    refs = ("no_provenance", "no_metadata", "no_authorization")
    forest(axes[0, 0], "output", "attacker_success", refs, "Output attack success | lower is better")
    forest(axes[0, 1], "output", "safe_completion", refs, "Output safe completion | higher is better")
    forest(axes[1, 0], "benign", "native_utility", refs, "Benign completion | higher is better")
    forest(axes[1, 1], "metadata", "safe_completion", refs, "Metadata safe completion | higher is better")
    fig.suptitle("Ablations | Complete TrustGate compared with one component removed", fontsize=15, x=.02, ha="left")
    finish(fig, "04_component_ablations",
        "Pointwise task-cluster 95% intervals; no multiple-comparison correction. Hollow diamonds mark degenerate empirical intervals.\n"
        "A [0, 0] interval from all-zero observations is not evidence of zero population risk or equivalence.")

    tasks = sorted({r["task"] for r in tables["task_metrics"]}, key=lambda t: int(t.rsplit("_", 1)[1]))
    indexed = {(r["task"], r["condition"]): r for r in tables["task_metrics"] if r["surface"] == "benign"}
    matrix = np.array([[indexed[t, c]["task_success_per_planned"] for c in CONDITIONS] for t in tasks])
    fig, ax = plt.subplots(figsize=(10, 9))
    display = ax.imshow(matrix, cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")
    workflow_names = {"W1": "Calendar read", "W2": "Email read", "W3": "File read",
                      "W4": "Calendar write", "W5": "File edit", "W6": "Cross-service"}
    ax.set(xticks=range(7), xticklabels=labels, yticks=range(len(tasks)),
           yticklabels=[f'{t.replace("user_task_", "Task ")} | '
                        f'{workflow_names[indexed[t, "none"]["workflow"].split("_")[0]]}' for t in tasks])
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
    for i, t in enumerate(tasks):
        for j, c in enumerate(CONDITIONS):
            ax.text(j, i, f'{indexed[t, c]["task_passes"]}/3', ha="center", va="center",
                    color="white" if matrix[i, j] > .55 else "#17243a", fontsize=9)
    fig.colorbar(display, ax=ax, fraction=.035, pad=.025, format=PercentFormatter(1))
    fig.suptitle("Benign task completion | Every task and condition", fontsize=16, x=.02, ha="left")
    finish(fig, "05_task_completion",
        "Each cell contains three repeated runs of one task. Repeats are not independent tasks.\n"
        "Task IDs and workflow labels refer to the frozen formal plan; results remain descriptive at this resolution.")

    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.7))
    resource = {r["condition"]: r for r in tables["resource_summary"]}
    for ax, metric, scale, title in zip(axes,
            ("mean_reported_cost_usd", "mean_model_calls", "mean_total_tokens"),
            (1000, 1, .001), ("Reported cost (milli-USD / trial)", "Model calls / trial", "Tokens (thousands / trial)")):
        values = [resource[c][metric] * scale for c in CONDITIONS]
        ax.barh(range(7), values, color=colors, height=.64)
        for i, value in enumerate(values):
            ax.text(value + max(values) * .02, i, f"{value:.2f}", va="center", fontsize=9)
        ax.set(yticks=range(7), yticklabels=labels, title=title, xlim=(0, max(values) * 1.25))
        ax.invert_yaxis()
        ax.xaxis.grid(True, alpha=.5)
        ax.set_axisbelow(True)
    fig.suptitle("Resources | Same 240 assigned trials per condition", fontsize=16, x=.02, ha="left")
    finish(fig, "06_resource_usage",
        "Includes all recorded statuses. Costs and tokens cover returned API usage; one timed-out request has unknown final billing.\n"
        "These are pooled descriptive means. Platform-adjusted latency and recovery sensitivity analyses are separate.")
    return produced


def write_readme(output, tables, include_figures=True):
    cells = {(r["surface"], r["condition"]): r for r in tables["main_metrics"]}
    lines = [
        "# Formal experiment result analysis", "",
        "This directory aggregates 1,680 formal records under the frozen plan: 20 tasks, seven configurations, three repetitions. Historical MVP, development trial runs, and offline simulation records are stored separately.",
        "Five CSV files, original receipts, formal lists, and existing ones `analysis.json` Remain unchanged.", "",
        "## Main results", "",
        "The normal task completion rate in the following table uses 60 planned records as the denominator; attack success rate uses valid records as the denominator; safe completion rate uses all 90 planned records as the denominator.", "",
        "| Configuration | Normal task completion | Output attack successful | Safe completion under output attack | Indication attack successful | Safe completion under indication attack |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    def display(n, d):
        return f"{n}/{d} ({100*n/d:.1f}%)"
    for condition in CONDITIONS:
        benign, output_row, metadata = [cells[s, condition] for s in SURFACES]
        lines.append("| " + " | ".join([ZH_LABELS[condition],
            display(benign["task_passes"], benign["planned"]),
            display(output_row["attack_successes"], output_row["valid"]),
            display(output_row["safe_completions"], output_row["planned"]),
            display(metadata["attack_successes"], metadata["valid"]),
            display(metadata["safe_completions"], metadata["planned"])]) + " |")
    lines += [
        "", "Complete TrustGate tool output attack record contains 1 item `TimeoutError`89 valid records, 90 recorded. This error remains in the planned sample denominator and is not counted as a successful defense.",
        "", "## Result interpretation", "",
        "1. **Evidence of protective benefit against tool output attacks.** Unprotected attacks succeeded in 10 out of 90, while full TrustGate achieved 0 out of 89 valid records; based on all planned records, safe completion was 61 out of 90 and 68 out of 90 respectively. Task pairing analysis is shown in Figure 3. Conclusions are limited to the current model, tasks, and attack distribution.",
        "2. **Uncertainty in normal task utility.** Full TrustGate completed 44 out of 60, unprotected completed 46 out of 60. Task-weighted difference is −3.33 percentage points, with individual 95% intervals of [−13.33, 6.67]; this does not constitute proof of utility equivalence or no loss.",
        "3. **Tool instruction attacks provide no distinguishing evidence of security benefit.** All seven configurations had 0 out of 90 successful attacks, and all 90 unprotected attacks were recorded as reaching the model. Attack strength, model behavior, and target judgment require trajectory-based interpretation; zero events do not equal universal safety.",
        "4. **Ablation results must be interpreted component by component.** Removing execution authorization led to 6 out of 90 successful output attacks; full system achieved 0 out of 89. The upper bound of the corresponding task pairing difference interval is 0, so the marginal benefit of this component cannot be described as having robust statistical confirmation. Removing source attribution or instruction screening also did not result in successful output attacks; current results are insufficient to prove that each module provides independent security gain.",
        "5. **Security, utility, and resource use must be reported together.** Classifier configuration completed 28 out of 60 normal tasks, lower than full TrustGate’s 44 out of 60; output attacks still succeeded in 13 out of 90. The mechanisms causing false positives and task failures due to screening are explained by subsequent trajectory verification.",
        "6. **Normal task failures are concentrated in specific tasks.** Tasks 2, 16, and 33 are 0/3 across all seven configurations; the full system for tasks 31 and 32 is 0/3, while without protection it is 2/3. These records are the focus of subsequent scoring and trajectory verification. Currently, only observed results are described without pre-assuming failure causes.",
        "", "## Chart", "",
    ]
    figures = [
        ("01_security_and_utility", "Safety and normal task completion rate", "First compare attack success and normal utility, noting the effective sample denominator."),
        ("02_safe_completion", "Safety completion rate under attack", "Use planned sample denominator, requiring both user task success and attack goal failure."),
        ("03_paired_comparisons", "Paired differences between the full system and three controls", "Error bars show per-item 95% intervals clustered by task."),
        ("04_component_ablations", "Three component ablations", "Compare the changes after removing source annotation, description screening, and execution authorization separately."),
        ("05_task_completion", "Per-task normal completion status", "Observe overall mean masking task differences with each cell representing three repetitions."),
        ("06_resource_usage", "Costs calls and tokens", "Use returned API usage; paired latency and platform layering are in separate overhead analysis."),
    ]
    for name, title, description in (figures if include_figures else []):
        lines += [f"### {title}", "", description, "",
                  f"![{title}](figures/{name}.png)", "",
                  f"[PDF](figures/{name}.pdf)", ""]
    lines += [
        "## Statistical definitions and reproduction", "",
        "- `tables/main_metrics.csv`: Count, completeness, planned/valid denominators, exposure, false positive proxy counts, and costs for 21 configuration and scenario units.",
        "- `tables/paired_comparisons.csv`: 30 paired differences, in percentage points; data directly from the paired results in the existing summary.",
        "- `tables/task_metrics.csv`: Counts and source platforms per task, configuration, and scenario.",
        "- `tables/resource_summary.csv`: 240 records per configuration for returned costs, number of calls, and tokens.",
        "- `tables/status_counts.csv`: Stop status distribution across five datasets.",
        "- `inputs.json`: Input file hashes and statistical rules for verifying the data version corresponding to the charts.",
        "",
        "Confidence intervals reuse the existing summarizer: first compute the mean of paired differences within each task, then perform 2,000 equal-weighted resamples across the 20 tasks with random seed 4213. The number of attack cases varies across tasks and one valid pair is missing, so task-weighted differences do not necessarily equal the direct subtraction of summary percentages.",
        "",
        "Intervals are exploratory per-item 95% intervals without multiple comparison correction. Bootstrap generates degenerate intervals when all observed differences are zero. [0, 0] Normal task authorization rejection counts serve as proxy metrics and do not yet equal manually confirmed false positive rates.",
        "",
        "Costs only cover API returned usage totaling $3.07556061; the final charge for one timeout request is unknown. Cross-platform raw timing comparisons are not made, and existing explanations for cache recovery and timing differences are not altered.",
        "",
        "Run on Python 3.10.20 Vanda PBS compute node at repository root directory:", "",
        "```bash",
        "python -m pip install -c requirements-runtime-constraints.txt -r requirements-analysis.txt",
        "python scripts/formal/analyze.py",
        "```", "",
        "Default output is to this directory. Use `--output runs/analysis-check` Can be reproduced in an isolated directory;`--tables-only` Only table generation is required; no plotting libraries are needed. Data reading, statistics, and plotting do not invoke model APIs.",
        "",
        "Subsequent analysis completed:[Trajectory verification](../review/README_ZH.md), [Tool instruction diagnosis](../metadata_diagnosis/README_ZH.md), [Mechanism analysis](../mechanism_evidence/README_ZH.md), [Overhead and recovery sensitivity](../overhead/README_ZH.md), [Legitimate call false positives](../false_positives/README_ZH.md). Complete research entry point is available at [Results overview](../../../docs/RESULTS_ZH.md).",
    ]
    (output / "README_ZH.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/formal/analysis")
    parser.add_argument("--tables-only", action="store_true")
    args = parser.parse_args()
    require_compute()
    plan = read_plan(ROOT / "assignments/formal/plan.json")
    manifest = load(ROOT / "results/formal/manifest.json")
    rows, input_hashes = read_deliveries(ROOT, plan, manifest)
    summary = original_summary_module().summarize(plan, rows)
    if summary != load(ROOT / "results/formal/analysis.json"):
        raise ValueError("Recomputed summary differs from the published analysis.json")
    tables = build_tables(plan, rows, summary)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "tables").mkdir(exist_ok=True)
    for name, records in tables.items():
        write_csv(args.output / "tables" / f"{name}.csv", records)
    figures = [] if args.tables_only else make_figures(tables, args.output)
    provenance = {
        "plan_sha256": plan["plan_sha256"],
        "analysis_script_sha256": sha(Path(__file__)),
        "python_version": sys.version.split()[0],
        "plot_packages": {name: importlib.metadata.version(name) for name in ("matplotlib", "numpy")} if not args.tables_only else {},
        "dataset_manifest_sha256": sha(ROOT / "results/formal/manifest.json"),
        "published_summary_sha256": sha(ROOT / "results/formal/analysis.json"),
        "delivery_csv_sha256": input_hashes,
        "recorded": len(rows), "valid": sum(not r["error_type"] for r in rows),
        "reported_cost_usd": format(sum((r["_cost_decimal"] for r in rows), Decimal(0)), ".8f"),
        "paired_interval_method": "Existing task-cluster percentile bootstrap; 2000 resamples; seed 4213",
        "multiple_comparison_adjustment": "none",
        "tables": {name: len(records) for name, records in tables.items()},
        "figures": figures,
    }
    (args.output / "inputs.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    write_readme(args.output, tables, include_figures=not args.tables_only)
    print(json.dumps({"records": len(rows), "tables": len(tables), "figures": len(figures),
                      "output": str(args.output), "model_api_calls": 0}))


if __name__ == "__main__":
    main()
