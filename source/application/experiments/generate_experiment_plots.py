"""Generate publication-ready experiment plots from benchmark artifacts.

This script reads the current benchmark JSON files and emits a bundle of PNG
figures for reports/papers.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]

PALETTE = {
    "blue": "#0072B2",
    "orange": "#E69F00",
    "green": "#009E73",
    "red": "#D55E00",
    "purple": "#CC79A7",
    "gray": "#4D4D4D",
    "light_blue": "#56B4E9",
}


def _setup_style() -> None:
    # Use conservative, publication-friendly defaults.
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif", "Times"],
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "figure.titlesize": 12,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "grid.alpha": 0.28,
            "grid.linewidth": 0.6,
            "grid.linestyle": "--",
        }
    )


def _format_k(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}k"
    return f"{value:.1f}"


def _shorten_tag(tag: str) -> str:
    replacements = {
        "current_default_scale1_m30": "default (scale1,m30)",
        "candidate_scale06_m19": "candidate (scale0.6,m19)",
        "candidate_scale06_m21": "candidate (scale0.6,m21)",
    }
    return replacements.get(tag, tag.replace("_", " "))


def _shorten_rule_engine_name(name: str) -> str:
    replacements = {
        "baseline_no_rule_no_engine": "baseline\n(no rule, no engine)",
        "rule_only_canonical_prune": "rule-only\n(canonical prune)",
        "engine_only_forced_closure": "engine-only\n(forced closure)",
        "full_optimized_rule_plus_engine": "full\n(rule + engine)",
    }
    return replacements.get(name, name.replace("_", "\n"))


def _shorten_feature_cfg(name: str) -> str:
    replacements = {
        "baseline_full_on": "baseline\n(full on)",
        "prune_safe_off": "prune_safe\noff",
        "immediate_undo_off": "immediate_undo\noff",
        "move_ordering_on": "move_ordering\non",
        "dominance_off": "dominance\noff",
        "move_interning_off": "move_interning\noff",
    }
    return replacements.get(name, name.replace("_", "\n"))


def _label_bars(ax: plt.Axes, bars, fmt: str = "{:.1f}") -> None:
    for b in bars:
        h = b.get_height()
        ax.annotate(
            fmt.format(h),
            xy=(b.get_x() + b.get_width() / 2, h),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing benchmark file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _sanitize_name(text: str) -> str:
    return (
        text.replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace("*", "star")
        .replace("%", "pct")
    )


def _save(fig: plt.Figure, output_dir: Path, filename: str) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / filename
    pdf_out = out.with_suffix(".pdf")
    fig.tight_layout()
    fig.savefig(out, dpi=300, bbox_inches="tight")
    fig.savefig(pdf_out, format="pdf", bbox_inches="tight")
    plt.close(fig)
    return str(out)


def _plot_overall_bfs_dfs(report: dict[str, Any], output_dir: Path) -> str:
    bfs_solved_ratio = 0.0
    bfs_cases = float(report["bfs_speed_summary"]["cases"])
    bfs_solved = float(report["bfs_speed_summary"]["solved_cases"])
    if bfs_cases > 0:
        bfs_solved_ratio = bfs_solved / bfs_cases

    dfs_solved_ratio = float(report["dfs_instability_summary"]["solved_ratio"])

    bfs_throughput = float(report["bfs_speed_summary"]["median_expanded_nodes_per_sec"])
    dfs_first_ms = float(report["dfs_instability_summary"]["first_solution_ms_median"])

    fig, axes = plt.subplots(1, 3, figsize=(12.0, 4.2))

    bars = axes[0].bar(
        ["BFS", "DFS"],
        [bfs_solved_ratio * 100.0, dfs_solved_ratio * 100.0],
        color=[PALETTE["red"], PALETTE["green"]],
    )
    axes[0].set_ylabel("Solved ratio (%)")
    axes[0].set_title("Solved Ratio")
    axes[0].set_ylim(0, 100)
    _label_bars(axes[0], bars, "{:.1f}")

    bars = axes[1].bar(["BFS"], [bfs_throughput], color=PALETTE["blue"])
    axes[1].set_title("BFS Throughput")
    axes[1].set_ylabel("Median expanded nodes/s")
    _label_bars(axes[1], bars, "{:.0f}")

    bars = axes[2].bar(["DFS"], [dfs_first_ms], color=PALETTE["orange"])
    axes[2].set_title("DFS First-Solution Latency")
    axes[2].set_ylabel("Median first-solution time (ms)")
    _label_bars(axes[2], bars, "{:.1f}")

    fig.suptitle("Overall Comparison: BFS/DFS Bottlenecks")
    return _save(fig, output_dir, "overall_bfs_dfs_summary.png")


def _plot_foundation_cost_sweep(summary_rows: list[dict[str, Any]], output_dir: Path) -> str:
    costs = [int(row["foundation_move_cost"]) for row in summary_rows]
    solved = [float(row["solved"]) for row in summary_rows]
    cases = [float(row["cases"]) for row in summary_rows]
    solved_ratio = [100.0 * (s / c if c > 0 else 0.0) for s, c in zip(solved, cases)]
    mean_elapsed = [float(row["mean_elapsed_ms_solved"]) for row in summary_rows]

    fig, ax1 = plt.subplots(figsize=(8.4, 4.8))
    ax2 = ax1.twinx()

    ax1.plot(costs, solved_ratio, marker="o", color=PALETTE["green"], linewidth=2.0, label="Solved ratio")
    ax2.plot(costs, mean_elapsed, marker="s", color=PALETTE["red"], linewidth=2.0, label="Mean solved time")

    ax1.set_xlabel("Foundation move cost")
    ax1.set_ylabel("Solved ratio (%)", color=PALETTE["green"])
    ax2.set_ylabel("Mean solved time (ms)", color=PALETTE["red"])
    ax1.set_title("UCS Cost Refinement Sweep")
    ax1.set_xticks(costs)

    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc="best")

    return _save(fig, output_dir, "tuning_foundation_cost_sweep.png")


def _plot_heuristic_tuning(astar_summary: list[dict[str, Any]], output_dir: Path) -> str:
    rows = sorted(astar_summary, key=lambda x: float(x["mean_elapsed_ms_solved"]))
    labels = [str(r["heuristic"]).replace("_", "\n") for r in rows]
    elapsed = [float(r["mean_elapsed_ms_solved"]) for r in rows]
    solved = [int(r["solved"]) for r in rows]
    speedup = [float(r["speedup_vs_combined_x"]) for r in rows]

    x = np.arange(len(labels))
    width = 0.32

    fig, ax1 = plt.subplots(figsize=(10.0, 4.8))
    ax2 = ax1.twinx()

    b1 = ax1.bar(x - width / 2, elapsed, width=width, color=PALETTE["blue"], label="Mean solved time (ms)")
    b2 = ax2.bar(x + width / 2, solved, width=width, color=PALETTE["green"], label="Solved cases")

    ax1.set_ylabel("Mean solved time (ms)")
    ax2.set_ylabel("Solved cases")
    ax2.set_ylim(0, max(solved) + 5)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.set_title("A* Heuristic Tuning")

    for i, sp in enumerate(speedup):
        ax1.text(
            x[i] - width / 2,
            elapsed[i] + max(elapsed) * 0.02,
            f"{sp:.2f}x",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    handles = [b1, b2]
    labels_leg = [h.get_label() for h in handles]
    ax1.legend(handles, labels_leg, loc="upper left")

    return _save(fig, output_dir, "tuning_astar_heuristics.png")


def _plot_sensitivity_head_to_head(head_to_head: dict[str, Any], output_dir: Path) -> str:
    rows = list(head_to_head.get("ranked", []))
    labels = [_shorten_tag(str(r["tag"])) for r in rows]
    elapsed = [float(r["mean_elapsed_ms_solved"]) for r in rows]
    solved = [int(r["solved"]) for r in rows]

    y = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    colors = [PALETTE["green"] if "m19" in lbl else PALETTE["blue"] for lbl in labels]
    bars = ax.barh(y, elapsed, color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Mean solved time (ms)")
    ax.set_title("Scale-vs-Magnitude Sensitivity (Head-to-head)")

    for i, bar in enumerate(bars):
        ax.text(
            bar.get_width() + 8.0,
            bar.get_y() + bar.get_height() / 2,
            f"solved={solved[i]}",
            va="center",
            fontsize=8,
        )

    return _save(fig, output_dir, "tuning_scale_magnitude_head_to_head.png")


def _plot_state_packing(state_packing: dict[str, Any], output_dir: Path) -> str:
    rows = state_packing["results"]
    algos = [str(r["algorithm"]) for r in rows]
    speedup = [float(r["packed_over_unpacked_speed_x"]) for r in rows]
    memory_ratio = [float(r["unpacked_over_packed_memory_x"]) for r in rows]

    x = np.arange(len(algos))
    width = 0.36

    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    b1 = ax.bar(x - width / 2, speedup, width=width, label="Speedup (packed/unpacked)", color=PALETTE["green"])
    b2 = ax.bar(x + width / 2, memory_ratio, width=width, label="Memory ratio (unpacked/packed)", color=PALETTE["orange"])
    ax.set_xticks(x)
    ax.set_xticklabels(algos)
    ax.set_ylabel("x ratio")
    ax.set_title("State Packing Impact")
    ax.legend()
    _label_bars(ax, b1, "{:.2f}")
    _label_bars(ax, b2, "{:.2f}")

    return _save(fig, output_dir, "optimization_state_packing.png")


def _plot_rule_engine_memory(rule_engine: dict[str, Any], output_dir: Path) -> str:
    rows = rule_engine["results"]
    labels = [_shorten_rule_engine_name(str(r["name"])) for r in rows]
    elapsed = [float(r["mean_elapsed_ms_solved"]) for r in rows]
    peak_heap = [float(r["mean_peak_heap_mb"]) for r in rows]
    generated = [float(r["mean_generated_nodes_solved"]) for r in rows]

    x = np.arange(len(labels))

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.8))

    bars0 = axes[0].bar(x, elapsed, color=PALETTE["red"])
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels)
    axes[0].set_ylabel("Mean solved time (ms)")
    axes[0].set_title("Rule/Engine Ablation: Time")
    _label_bars(axes[0], bars0, "{:.0f}")

    axm = axes[1]
    axg = axm.twinx()
    bars1 = axm.bar(x, peak_heap, color=PALETTE["purple"], label="Peak heap (MB)")
    line1 = axg.plot(
        x,
        np.array(generated) / 1000.0,
        color=PALETTE["green"],
        marker="o",
        linewidth=2.0,
        label="Generated nodes (k)",
    )
    axm.set_xticks(x)
    axm.set_xticklabels(labels)
    axm.set_ylabel("Peak heap (MB)")
    axg.set_ylabel("Generated nodes (thousands)")
    axm.set_title("Rule/Engine Ablation: Memory and Work")
    _label_bars(axm, bars1, "{:.1f}")
    handles = [bars1, line1[0]]
    axm.legend(handles, [h.get_label() for h in handles], loc="upper right")

    fig.suptitle("UCS Rule/Engine Joint Ablation")
    return _save(fig, output_dir, "optimization_rule_engine_ablation.png")


def _plot_feature_ablation(feature_report: dict[str, Any], output_dir: Path) -> str:
    summary = feature_report["summary"]
    by_cfg = summary["summary_by_config"]
    delta = summary["delta_vs_baseline_full_on"]

    cfg_names = list(by_cfg.keys())
    cfg_labels = [_shorten_feature_cfg(c) for c in cfg_names]
    elapsed = [float(by_cfg[c]["mean_elapsed_ms_all"]) for c in cfg_names]
    elapsed_delta = [float(delta[c]["elapsed_improve_pct_vs_baseline"]) for c in cfg_names]
    generated_delta = [float(delta[c]["generated_reduction_pct_vs_baseline"]) for c in cfg_names]

    x = np.arange(len(cfg_names))

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.8))

    b0 = axes[0].bar(x, elapsed, color=PALETTE["blue"])
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(cfg_labels)
    axes[0].set_ylabel("Mean elapsed (ms)")
    axes[0].set_title("Engine/UCS Feature Ablation: Time")
    _label_bars(axes[0], b0, "{:.1f}")

    axes[1].axhline(0.0, color="gray", linewidth=1)
    b1 = axes[1].bar(x - 0.18, elapsed_delta, width=0.35, label="Elapsed improve %", color=PALETTE["purple"])
    b2 = axes[1].bar(x + 0.18, generated_delta, width=0.35, label="Generated reduction %", color=PALETTE["light_blue"])
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(cfg_labels)
    axes[1].set_title("Delta vs Baseline (higher is better)")
    axes[1].legend()
    _label_bars(axes[1], b1, "{:.1f}")
    _label_bars(axes[1], b2, "{:.1f}")

    fig.suptitle("Safe Toggle Ablation for UCS/Engine")
    return _save(fig, output_dir, "optimization_engine_ucs_feature_ablation.png")


def _plot_microbenchmark(micro: dict[str, Any], output_dir: Path) -> str:
    model = micro["results"]["model"]
    rule = micro["results"]["rule"]

    model_labels = ["from_lists", "transition_inc", "transition_rebuild"]
    model_tp = [
        float(model["state_create_from_lists"]["throughput_ops_per_sec"]),
        float(model["state_transition_incremental"]["throughput_ops_per_sec"]),
        float(model["state_transition_full_rebuild"]["throughput_ops_per_sec"]),
    ]

    rule_labels = ["pair_lookup", "pair_naive", "seq_warm", "seq_cold"]
    rule_tp = [
        float(rule["tableau_pair_lookup"]["lookup_ops_per_sec"]),
        float(rule["tableau_pair_lookup"]["naive_ops_per_sec"]),
        float(rule["movable_sequences_cache"]["warm_ops_per_sec"]),
        float(rule["movable_sequences_cache"]["cold_ops_per_sec"]),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.8))

    bm = axes[0].bar(model_labels, model_tp, color=PALETTE["orange"])
    axes[0].set_title("Model Primitive Throughput")
    axes[0].set_ylabel("ops/s")
    axes[0].tick_params(axis="x", rotation=0)
    _label_bars(axes[0], bm, "{:.0f}")

    br = axes[1].bar(rule_labels, rule_tp, color=PALETTE["gray"])
    axes[1].set_title("Rule Primitive Throughput")
    axes[1].set_ylabel("ops/s")
    axes[1].tick_params(axis="x", rotation=0)
    _label_bars(axes[1], br, "{:.0f}")

    fig.suptitle("Model/Rule Microbenchmark")
    return _save(fig, output_dir, "optimization_model_rule_microbenchmark.png")


def _load_algorithm_profile_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing algorithm profile file: {path}")

    if path.suffix.lower() == ".csv":
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))
        return rows

    data = _load_json(path)
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        return list(data["rows"])

    raise ValueError(
        "Algorithm profile must be a CSV with row records or a JSON containing 'rows'."
    )


def _plot_algorithm_metric_boxplot(
    rows: list[dict[str, Any]],
    *,
    metric_key: str,
    ylabel: str,
    title: str,
    filename: str,
    output_dir: Path,
) -> str:
    algorithm_order = ["A*", "BFS", "DFS", "UCS"]
    colors = {
        "A*": PALETTE["blue"],
        "BFS": PALETTE["orange"],
        "DFS": PALETTE["green"],
        "UCS": PALETTE["red"],
    }

    labels: list[str] = []
    data: list[list[float]] = []
    for algorithm in algorithm_order:
        values: list[float] = []
        for row in rows:
            if str(row.get("algorithm", "")) != algorithm:
                continue
            val = row.get(metric_key)
            if val is None:
                continue
            try:
                numeric = float(val)
            except (TypeError, ValueError):
                continue
            if numeric > 0:
                values.append(numeric)
        if values:
            labels.append(algorithm)
            data.append(values)

    if not data:
        raise ValueError(f"No numeric values found for metric '{metric_key}'")

    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    bp = ax.boxplot(data, tick_labels=labels, patch_artist=True, showfliers=True)

    for patch, label in zip(bp["boxes"], labels):
        patch.set_facecolor(colors[label])
        patch.set_alpha(0.55)
        patch.set_edgecolor(PALETTE["gray"])

    for median in bp["medians"]:
        median.set_color("black")
        median.set_linewidth(1.4)

    ax.set_yscale("log")
    ax.set_xlabel("Algorithm")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(axis="y", which="both", alpha=0.25)

    return _save(fig, output_dir, filename)


def _plot_nodes_vs_metric_for_algorithms(
    rows: list[dict[str, Any]],
    *,
    metric_key: str,
    ylabel: str,
    title_prefix: str,
    filename: str,
    output_dir: Path,
) -> str:
    algorithms = ["A*", "DFS"]
    colors = {"A*": PALETTE["blue"], "DFS": PALETTE["green"]}

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.8))
    for idx, algorithm in enumerate(algorithms):
        points: list[tuple[float, float]] = []
        for row in rows:
            if str(row.get("algorithm", "")) != algorithm:
                continue
            try:
                x = float(row.get("expanded_nodes"))
                y = float(row.get(metric_key))
            except (TypeError, ValueError):
                continue
            if x > 0 and y > 0:
                points.append((x, y))

        if not points:
            continue

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        axes[idx].scatter(
            xs,
            ys,
            s=36,
            alpha=0.8,
            color=colors[algorithm],
            edgecolors="none",
        )
        axes[idx].set_xlabel("Expanded Nodes")
        axes[idx].set_ylabel(ylabel)
        axes[idx].set_title(f"{title_prefix}: {algorithm}")
        axes[idx].grid(alpha=0.25)

    return _save(fig, output_dir, filename)


def _default_output_dir() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return ROOT / "benchmark_results" / f"experiment_plots_{ts}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate visualization plots for experiment report")
    parser.add_argument("--output-dir", type=str, default="", help="Output directory (default: benchmark_results/experiment_plots_<timestamp>)")

    parser.add_argument(
        "--bfs-dfs-report",
        type=str,
        default="benchmark_results/bfs_dfs_bottlenecks_20260404_210450/report.json",
    )
    parser.add_argument(
        "--ucs-refine-summary",
        type=str,
        default="benchmark_results/refine_minus10_to_minus100/ucs_summary_minus10_to_minus100.json",
    )
    parser.add_argument(
        "--astar-summary",
        type=str,
        default="benchmark_results/tuning_20260403_211853/astar_summary.json",
    )
    parser.add_argument(
        "--sensitivity-head2head",
        type=str,
        default="benchmark_results/sensitivity_scale_vs_magnitude/head_to_head_1_30_timeout10.json",
    )
    parser.add_argument(
        "--state-packing",
        type=str,
        default="benchmark_results/optimization_ablation_20260405/state_packing_deal1_trials3_maxexpand30000.json",
    )
    parser.add_argument(
        "--rule-engine-memory",
        type=str,
        default="benchmark_results/optimization_ablation_20260405/ucs_rule_engine_ablation_with_memory_deal1_trials5.json",
    )
    parser.add_argument(
        "--feature-ablation",
        type=str,
        default="benchmark_results/engine_ucs_feature_ablation_20260405_153102/report.json",
    )
    parser.add_argument(
        "--microbenchmark",
        type=str,
        default="benchmark_results/model_rule_micro_20260405_153025/report.json",
    )
    parser.add_argument(
        "--algorithm-profile",
        type=str,
        default="",
        help=(
            "Optional algorithm profile rows file (CSV or report JSON with rows) "
            "for additional boxplot/scatter figures."
        ),
    )
    return parser


def main() -> None:
    _setup_style()
    parser = _build_parser()
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else _default_output_dir()
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir

    bfs_dfs_report = _load_json(ROOT / args.bfs_dfs_report)
    ucs_refine = _load_json(ROOT / args.ucs_refine_summary)
    astar_summary = _load_json(ROOT / args.astar_summary)
    sensitivity = _load_json(ROOT / args.sensitivity_head2head)
    state_packing = _load_json(ROOT / args.state_packing)
    rule_engine = _load_json(ROOT / args.rule_engine_memory)
    feature_ablation = _load_json(ROOT / args.feature_ablation)
    microbenchmark = _load_json(ROOT / args.microbenchmark)

    generated: list[str] = []
    generated.append(_plot_overall_bfs_dfs(bfs_dfs_report, output_dir))
    generated.append(_plot_foundation_cost_sweep(ucs_refine, output_dir))
    generated.append(_plot_heuristic_tuning(astar_summary, output_dir))
    generated.append(_plot_sensitivity_head_to_head(sensitivity, output_dir))
    generated.append(_plot_state_packing(state_packing, output_dir))
    generated.append(_plot_rule_engine_memory(rule_engine, output_dir))
    generated.append(_plot_feature_ablation(feature_ablation, output_dir))
    generated.append(_plot_microbenchmark(microbenchmark, output_dir))

    if args.algorithm_profile:
        algorithm_profile_path = Path(args.algorithm_profile)
        if not algorithm_profile_path.is_absolute():
            algorithm_profile_path = ROOT / algorithm_profile_path
        profile_rows = _load_algorithm_profile_rows(algorithm_profile_path)

        generated.append(
            _plot_algorithm_metric_boxplot(
                profile_rows,
                metric_key="peak_memory_mb",
                ylabel="Peak Memory (MB, log scale)",
                title="Algorithm Comparison: Peak Memory",
                filename="algorithm_peak_memory_boxplot.png",
                output_dir=output_dir,
            )
        )
        generated.append(
            _plot_nodes_vs_metric_for_algorithms(
                profile_rows,
                metric_key="peak_memory_mb",
                ylabel="Peak Memory (MB)",
                title_prefix="Nodes vs Peak Memory",
                filename="nodes_vs_peak_memory_astar_dfs.png",
                output_dir=output_dir,
            )
        )
        generated.append(
            _plot_algorithm_metric_boxplot(
                profile_rows,
                metric_key="elapsed_s",
                ylabel="Search Time (s, log scale)",
                title="Algorithm Comparison: Search Time",
                filename="algorithm_search_time_boxplot.png",
                output_dir=output_dir,
            )
        )
        generated.append(
            _plot_nodes_vs_metric_for_algorithms(
                profile_rows,
                metric_key="elapsed_s",
                ylabel="Search Time (s)",
                title_prefix="Nodes vs Search Time",
                filename="nodes_vs_search_time_astar_dfs.png",
                output_dir=output_dir,
            )
        )

    manifest = {
        "output_dir": str(output_dir),
        "count": len(generated),
        "files": generated,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
