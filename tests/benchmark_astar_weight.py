"""Benchmark Weighted A* across many deals and export CSV reports.

Outputs
-------
- Detailed CSV: one row per (deal, weight).
- Summary CSV: one row per weight with aggregated metrics.

Recommendation policy
---------------------
- speed: maximize solved count, then minimize average elapsed time.
- quality: maximize solved count, then minimize average solution cost,
  then minimize average solution length.
"""

import argparse
import csv
import os
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.engine.shuffle import deal_by_game_number
from backend.model.state import State
from backend.solver.astar import AStarAlgorithm
from backend.solver.heuristics import combined_heuristic


@dataclass(frozen=True)
class BenchmarkRun:
    deal: int
    weight: float
    solved: bool
    elapsed_s: float
    solution_length: int | None
    solution_cost: int | None
    expanded_nodes: int
    generated_nodes: int
    stale_heap_pops: int
    pruned_by_cost: int
    pruned_by_closed: int
    reopened_nodes: int
    peak_frontier_size: int
    peak_closed_size: int
    final_frontier_size: int
    final_closed_size: int
    move_pool_size: int
    effective_branching_factor: float
    cost_prune_rate: float
    closed_prune_rate: float


def _parse_weight_list(text: str) -> list[float]:
    values = [item.strip() for item in text.split(",") if item.strip()]
    if not values:
        raise ValueError("--weights must contain at least one numeric value")
    parsed = [float(item) for item in values]
    if any(weight <= 0 for weight in parsed):
        raise ValueError("All weights must be > 0")
    return parsed


def _build_initial_state(deal_number: int) -> State:
    tableau = deal_by_game_number(deal_number)
    return State.from_lists(tableau=tableau, freecells=[None] * 4, foundations=[[] for _ in range(4)])


def _mean(values: Iterable[float]) -> float | None:
    data = list(values)
    if not data:
        return None
    return float(statistics.mean(data))


def _median(values: Iterable[float]) -> float | None:
    data = list(values)
    if not data:
        return None
    return float(statistics.median(data))


def _safe_float(value: float | None, precision: int = 6) -> str:
    if value is None:
        return ""
    return f"{value:.{precision}f}"


def _safe_int(value: int | None) -> str:
    return "" if value is None else str(value)


def _summarize_weight(weight: float, runs: list[BenchmarkRun]) -> dict:
    solved_runs = [run for run in runs if run.solved]
    solved_count = len(solved_runs)
    total = len(runs)
    return {
        "weight": weight,
        "deals": total,
        "solved": solved_count,
        "solve_rate": solved_count / max(total, 1),
        "avg_elapsed_s": _mean(run.elapsed_s for run in runs),
        "median_elapsed_s": _median(run.elapsed_s for run in runs),
        "avg_solution_length": _mean(run.solution_length for run in solved_runs if run.solution_length is not None),
        "avg_solution_cost": _mean(run.solution_cost for run in solved_runs if run.solution_cost is not None),
        "avg_expanded_nodes": _mean(run.expanded_nodes for run in runs),
        "avg_generated_nodes": _mean(run.generated_nodes for run in runs),
        "avg_peak_frontier": _mean(run.peak_frontier_size for run in runs),
        "avg_peak_closed": _mean(run.peak_closed_size for run in runs),
        "avg_final_frontier": _mean(run.final_frontier_size for run in runs),
        "avg_final_closed": _mean(run.final_closed_size for run in runs),
        "avg_reopened_nodes": _mean(run.reopened_nodes for run in runs),
        "avg_effective_branching_factor": _mean(run.effective_branching_factor for run in runs),
        "avg_cost_prune_rate": _mean(run.cost_prune_rate for run in runs),
        "avg_closed_prune_rate": _mean(run.closed_prune_rate for run in runs),
    }


def _pick_best_speed(summary_rows: list[dict]) -> dict:
    return max(
        summary_rows,
        key=lambda row: (
            row["solved"],
            -(row["avg_elapsed_s"] if row["avg_elapsed_s"] is not None else float("inf")),
            -(row["median_elapsed_s"] if row["median_elapsed_s"] is not None else float("inf")),
        ),
    )


def _pick_best_quality(summary_rows: list[dict]) -> dict:
    return max(
        summary_rows,
        key=lambda row: (
            row["solved"],
            -(row["avg_solution_cost"] if row["avg_solution_cost"] is not None else float("inf")),
            -(row["avg_solution_length"] if row["avg_solution_length"] is not None else float("inf")),
            -(row["avg_elapsed_s"] if row["avg_elapsed_s"] is not None else float("inf")),
        ),
    )


def _write_detailed_csv(path: Path, runs: list[BenchmarkRun]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "deal",
                "weight",
                "solved",
                "elapsed_s",
                "solution_length",
                "solution_cost",
                "expanded_nodes",
                "generated_nodes",
                "stale_heap_pops",
                "pruned_by_cost",
                "pruned_by_closed",
                "reopened_nodes",
                "peak_frontier_size",
                "peak_closed_size",
                "final_frontier_size",
                "final_closed_size",
                "move_pool_size",
                "effective_branching_factor",
                "cost_prune_rate",
                "closed_prune_rate",
            ]
        )
        for run in runs:
            writer.writerow(
                [
                    run.deal,
                    f"{run.weight:.3f}",
                    int(run.solved),
                    f"{run.elapsed_s:.6f}",
                    _safe_int(run.solution_length),
                    _safe_int(run.solution_cost),
                    run.expanded_nodes,
                    run.generated_nodes,
                    run.stale_heap_pops,
                    run.pruned_by_cost,
                    run.pruned_by_closed,
                    run.reopened_nodes,
                    run.peak_frontier_size,
                    run.peak_closed_size,
                    run.final_frontier_size,
                    run.final_closed_size,
                    run.move_pool_size,
                    f"{run.effective_branching_factor:.6f}",
                    f"{run.cost_prune_rate:.6f}",
                    f"{run.closed_prune_rate:.6f}",
                ]
            )


def _write_summary_csv(path: Path, summary_rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "weight",
                "deals",
                "solved",
                "solve_rate",
                "avg_elapsed_s",
                "median_elapsed_s",
                "avg_solution_length",
                "avg_solution_cost",
                "avg_expanded_nodes",
                "avg_generated_nodes",
                "avg_peak_frontier",
                "avg_peak_closed",
                "avg_final_frontier",
                "avg_final_closed",
                "avg_reopened_nodes",
                "avg_effective_branching_factor",
                "avg_cost_prune_rate",
                "avg_closed_prune_rate",
            ]
        )
        for row in summary_rows:
            writer.writerow(
                [
                    f"{row['weight']:.3f}",
                    row["deals"],
                    row["solved"],
                    _safe_float(row["solve_rate"], precision=4),
                    _safe_float(row["avg_elapsed_s"]),
                    _safe_float(row["median_elapsed_s"]),
                    _safe_float(row["avg_solution_length"], precision=3),
                    _safe_float(row["avg_solution_cost"], precision=3),
                    _safe_float(row["avg_expanded_nodes"], precision=3),
                    _safe_float(row["avg_generated_nodes"], precision=3),
                    _safe_float(row["avg_peak_frontier"], precision=3),
                    _safe_float(row["avg_peak_closed"], precision=3),
                    _safe_float(row["avg_final_frontier"], precision=3),
                    _safe_float(row["avg_final_closed"], precision=3),
                    _safe_float(row["avg_reopened_nodes"], precision=3),
                    _safe_float(row["avg_effective_branching_factor"], precision=6),
                    _safe_float(row["avg_cost_prune_rate"], precision=6),
                    _safe_float(row["avg_closed_prune_rate"], precision=6),
                ]
            )


def _print_detailed_runs(grouped_runs: dict[float, list[BenchmarkRun]]) -> None:
    print("\nDetailed per-run metrics")
    print(
        "weight,deal,solved,elapsed_s,solution_length,solution_cost,"
        "expanded_nodes,generated_nodes,stale_heap_pops,pruned_by_cost,"
        "pruned_by_closed,reopened_nodes,peak_frontier_size,peak_closed_size,"
        "final_frontier_size,final_closed_size,move_pool_size,"
        "effective_branching_factor,cost_prune_rate,closed_prune_rate"
    )
    for weight in sorted(grouped_runs.keys()):
        for run in sorted(grouped_runs[weight], key=lambda item: item.deal):
            print(
                f"{run.weight:.3f},{run.deal},{int(run.solved)},{run.elapsed_s:.6f},"
                f"{_safe_int(run.solution_length)},{_safe_int(run.solution_cost)},"
                f"{run.expanded_nodes},{run.generated_nodes},{run.stale_heap_pops},"
                f"{run.pruned_by_cost},{run.pruned_by_closed},{run.reopened_nodes},"
                f"{run.peak_frontier_size},{run.peak_closed_size},{run.final_frontier_size},"
                f"{run.final_closed_size},{run.move_pool_size},"
                f"{run.effective_branching_factor:.6f},{run.cost_prune_rate:.6f},"
                f"{run.closed_prune_rate:.6f}"
            )


def _print_summary(summary_rows: list[dict], speed_best: dict, quality_best: dict) -> None:
    print("\nA* weight benchmark summary")
    print("weight | solved/deals | solve_rate | avg_elapsed_s | avg_cost | avg_len")
    print("-" * 75)
    for row in summary_rows:
        avg_cost = "n/a" if row["avg_solution_cost"] is None else f"{row['avg_solution_cost']:.2f}"
        avg_len = "n/a" if row["avg_solution_length"] is None else f"{row['avg_solution_length']:.2f}"
        avg_elapsed = "n/a" if row["avg_elapsed_s"] is None else f"{row['avg_elapsed_s']:.3f}"
        print(
            f"{row['weight']:>6.2f} | "
            f"{row['solved']:>2}/{row['deals']:<2}        | "
            f"{row['solve_rate']:.3f}     | "
            f"{avg_elapsed:>12} | "
            f"{avg_cost:>8} | "
            f"{avg_len:>7}"
        )

    print("\nRecommended defaults")
    print(f"- speed   -> weight={speed_best['weight']:.2f}")
    print(f"- quality -> weight={quality_best['weight']:.2f}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Weighted A* and export CSV reports")
    parser.add_argument("--deal-start", type=int, default=151, help="First deal number (inclusive)")
    parser.add_argument("--deal-end", type=int, default=170, help="Last deal number (inclusive)")
    parser.add_argument(
        "--weights",
        type=str,
        default="3,4,5,6,7",
        help="Comma-separated weights (example: 3,4,5,6,7)",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=None,
        help="Per-run timeout in seconds via should_cancel (omit for no timeout)",
    )
    parser.add_argument(
        "--print-all-runs",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Print every run's full metrics to console for direct comparison",
    )
    parser.add_argument(
        "--output-prefix",
        type=str,
        default="tests/benchmarks/astar_weight_benchmark",
        help="Path prefix for CSV files (without extension)",
    )
    args = parser.parse_args()

    if args.deal_end < args.deal_start:
        raise ValueError("--deal-end must be >= --deal-start")
    if args.timeout_s is not None and args.timeout_s <= 0:
        raise ValueError("--timeout-s must be > 0 when provided")

    weights = _parse_weight_list(args.weights)
    deals = list(range(args.deal_start, args.deal_end + 1))

    os.environ["ASTAR_RUNTIME_LOG"] = "0"

    runs: list[BenchmarkRun] = []
    grouped_runs: dict[float, list[BenchmarkRun]] = {weight: [] for weight in weights}

    total_runs = len(weights) * len(deals)
    completed = 0
    started_at = perf_counter()

    for weight in weights:
        for deal in deals:
            state = _build_initial_state(deal)
            run_started = perf_counter()
            if args.timeout_s is None:
                should_cancel = lambda: False
            else:
                should_cancel = lambda run_started=run_started: (perf_counter() - run_started) >= args.timeout_s

            solver = AStarAlgorithm(
                state,
                heuristic_func=combined_heuristic,
                weight=weight,
                should_cancel=should_cancel,
            )
            path = solver.search()
            elapsed_s = perf_counter() - run_started
            stats = solver.last_run_stats or {}

            run = BenchmarkRun(
                deal=deal,
                weight=weight,
                solved=path is not None,
                elapsed_s=elapsed_s,
                solution_length=len(path) if path is not None else None,
                solution_cost=stats.get("solution_cost"),
                expanded_nodes=stats.get("expanded_nodes", 0),
                generated_nodes=stats.get("generated_nodes", 0),
                stale_heap_pops=stats.get("stale_heap_pops", 0),
                pruned_by_cost=stats.get("pruned_by_cost", 0),
                pruned_by_closed=stats.get("pruned_by_closed", 0),
                reopened_nodes=stats.get("reopened_nodes", 0),
                peak_frontier_size=stats.get("peak_frontier_size", 0),
                peak_closed_size=stats.get("peak_closed_size", 0),
                final_frontier_size=stats.get("final_frontier_size", 0),
                final_closed_size=stats.get("final_closed_size", 0),
                move_pool_size=stats.get("move_pool_size", 0),
                effective_branching_factor=stats.get("effective_branching_factor", 0.0),
                cost_prune_rate=stats.get("cost_prune_rate", 0.0),
                closed_prune_rate=stats.get("closed_prune_rate", 0.0),
            )
            runs.append(run)
            grouped_runs[weight].append(run)

            completed += 1
            if completed % max(1, len(deals) // 4) == 0 or completed == total_runs:
                elapsed_total = perf_counter() - started_at
                print(
                    f"Progress: {completed}/{total_runs} runs "
                    f"({(completed / total_runs) * 100:.1f}%) in {elapsed_total:.1f}s"
                )

    summary_rows = [_summarize_weight(weight, grouped_runs[weight]) for weight in weights]
    speed_best = _pick_best_speed(summary_rows)
    quality_best = _pick_best_quality(summary_rows)

    output_prefix = Path(args.output_prefix)
    detailed_path = output_prefix.with_suffix(".csv")
    summary_path = output_prefix.with_name(f"{output_prefix.name}_summary").with_suffix(".csv")

    _write_detailed_csv(detailed_path, runs)
    _write_summary_csv(summary_path, summary_rows)
    if args.print_all_runs:
        _print_detailed_runs(grouped_runs)
    _print_summary(summary_rows, speed_best, quality_best)

    print("\nCSV outputs")
    print(f"- detailed: {detailed_path}")
    print(f"- summary : {summary_path}")
    print("\nSet objective defaults")
    print(f"- speed   : ASTAR_OBJECTIVE=speed   (mapped to weight={speed_best['weight']:.2f})")
    print(f"- quality : ASTAR_OBJECTIVE=quality (mapped to weight={quality_best['weight']:.2f})")
    if args.timeout_s is None:
        print("- timeout : disabled (run until solve/exhaust)")
    else:
        print(f"- timeout : {args.timeout_s:.3f}s per run")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
