"""Create reproducible tables and figures from the five frozen public deliveries."""
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
    "none": "无防护", "delimiters": "提示防护", "classifier": "分类器",
    "trustgate": "完整 TrustGate", "no_provenance": "去掉来源标注",
    "no_metadata": "去掉说明筛查", "no_authorization": "去掉执行授权",
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
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
        "# 正式实验结果分析", "",
        "本目录汇总冻结计划下的 1,680 条正式记录：20 个任务、七种配置、三次重复。历史 MVP、开发试跑及离线模拟记录单独保存。",
        "五份 CSV、原始收据、正式清单与既有 `analysis.json` 保持不变。", "",
        "## 主要结果", "",
        "下表正常任务完成率以 60 条计划记录为分母；攻击成功率以有效记录为分母；安全完成率以全部 90 条计划记录为分母。", "",
        "| 配置 | 正常任务完成 | 输出攻击成功 | 输出攻击下安全完成 | 说明攻击成功 | 说明攻击下安全完成 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    def display(n, d):
        return f"{n}/{d}（{100*n/d:.1f}%）"
    for condition in CONDITIONS:
        benign, output_row, metadata = [cells[s, condition] for s in SURFACES]
        lines.append("| " + " | ".join([ZH_LABELS[condition],
            display(benign["task_passes"], benign["planned"]),
            display(output_row["attack_successes"], output_row["valid"]),
            display(output_row["safe_completions"], output_row["planned"]),
            display(metadata["attack_successes"], metadata["valid"]),
            display(metadata["safe_completions"], metadata["planned"])]) + " |")
    lines += [
        "", "完整 TrustGate 的工具输出攻击记录包含 1 条 `TimeoutError`：89 条有效、90 条已记录。该错误保留在计划样本分母中，不计作成功防御。",
        "", "## 结果解释", "",
        "1. **工具输出攻击存在防护收益的证据。**无防护攻击成功 10/90，完整 TrustGate 为 0/89 有效记录；按全部计划记录计算，安全完成分别为 61/90 与 68/90。任务配对分析见图 3。结论限定于当前模型、任务与攻击分布。",
        "2. **正常任务效用存在不确定性。**完整 TrustGate 完成 44/60，无防护完成 46/60。任务加权差异为 −3.33 个百分点，逐项 95% 区间为 [−13.33, 6.67]；这不构成效用等价或无损失的证明。",
        "3. **工具说明攻击未提供安全收益的区分证据。**全部七种配置攻击成功均为 0/90，且无防护的 90 次攻击均记录为到达模型。需要结合轨迹解释攻击强度、模型行为和目标判定；零事件不等于普遍安全。",
        "4. **消融结果需按组件分别解释。**去掉执行授权后，输出攻击成功为 6/90；完整系统为 0/89。对应任务配对差异区间上界为 0，不能将该组件的边际收益描述为已获得稳健统计确认。去掉来源标注或说明筛查后也未观察到输出攻击成功，当前结果不足以证明每个模块都有独立安全增益。",
        "5. **安全、效用与资源要共同报告。**分类器配置的正常任务完成为 28/60，低于完整 TrustGate 的 44/60；输出攻击仍成功 13/90。筛查造成的误报和任务失败机制由后续轨迹核查解释。",
        "6. **正常任务失败集中在部分任务。**任务 2、16、33 在七种配置下均为 0/3；任务 31、32 的完整系统为 0/3，无防护均为 2/3。这些记录是后续评分与轨迹核查的重点，目前仅描述观测结果，不预设失败原因。",
        "", "## 图表", "",
    ]
    figures = [
        ("01_security_and_utility", "安全性与正常任务完成率", "先比较攻击成功与正常效用，注意有效样本分母。"),
        ("02_safe_completion", "攻击下安全完成率", "使用计划样本分母，同时要求用户任务成功和攻击目标失败。"),
        ("03_paired_comparisons", "完整系统与三种对照的配对差异", "误差线显示按任务聚类的逐项 95% 区间。"),
        ("04_component_ablations", "三项组件消融", "分别比较移除来源标注、说明筛查和执行授权后的变化。"),
        ("05_task_completion", "逐任务正常完成情况", "观察总体均值掩盖的任务差异，每格为三次重复。"),
        ("06_resource_usage", "费用、调用数与 token", "使用已返回 API 使用量；跨平台延迟留待单独分析。"),
    ]
    for name, title, description in (figures if include_figures else []):
        lines += [f"### {title}", "", description, "",
                  f"![{title}](figures/{name}.png)", "",
                  f"[PDF](figures/{name}.pdf)", ""]
    lines += [
        "## 统计口径与复现", "",
        "- `tables/main_metrics.csv`：21 个配置与场景单元的计数、完整性、计划/有效分母、曝光、误报代理量和费用。",
        "- `tables/paired_comparisons.csv`：30 项配对差异，单位为百分点；数据原样来自既有汇总中的配对结果。",
        "- `tables/task_metrics.csv`：逐任务、配置和场景的计数与来源平台。",
        "- `tables/resource_summary.csv`：每种配置 240 条记录的已返回费用、调用数与 token。",
        "- `tables/status_counts.csv`：五份数据的停止状态分布。",
        "- `inputs.json`：输入文件哈希与统计规则，便于验证图表对应的数据版本。",
        "",
        "置信区间沿用既有汇总器：先在任务内计算成对差异的均值，再对 20 个任务等权重采样 2,000 次，随机种子 4213。攻击案例数量在任务间不完全相同，且存在一个缺失的有效配对，因此任务加权差异不一定等于汇总百分比直接相减。",
        "",
        "区间为探索性的逐项 95% 区间，未做多重比较校正。全部观测差异为零时 bootstrap 会生成 [0, 0] 的退化区间；它不能证明总体风险为零或两种方法等价。正常任务中的授权拒绝次数属于代理指标，尚不等于人工确认的误报率。",
        "",
        "费用只覆盖 API 已返回使用量，总和为 $3.07556061；一次超时请求的最终收费未知。这里不比较跨平台原始耗时，也不改变缓存恢复与计时差异的既有说明。",
        "",
        "在 Python 3.10.20 的 Vanda PBS 计算节点、仓库根目录运行：", "",
        "```bash",
        "python -m pip install -c requirements-runtime-constraints.txt -r requirements-analysis.txt",
        "python scripts/formal/analyze.py",
        "```", "",
        "默认输出为本目录。使用 `--output runs/analysis-check` 可以在独立目录复现；`--tables-only` 仅生成表格，不需要绘图库。数据读取、统计和绘图均不调用模型 API。",
        "",
        "轨迹抽查、工具说明攻击诊断、平台与恢复计时敏感性分析，以及演示材料属于后续分析范围。",
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
