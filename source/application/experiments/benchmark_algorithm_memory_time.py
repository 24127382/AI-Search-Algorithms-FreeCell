"""Benchmark algorithm-level time and memory for plotting-style comparisons.

This benchmark captures per-run rows with:
- expanded nodes
- elapsed time
- peak Python heap (tracemalloc)

It is intended to feed boxplots/scatter plots like:
- algorithm comparison (peak memory, search time)
- nodes vs metric (A* and DFS)
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import os
import sys
import tracemalloc
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Callable

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import engine first to avoid known service/solver circular-import bootstrap issue.
import source.application.engine.engine  # noqa: F401
import source.domain.solver.astar as astar_module
import source.domain.solver.bfs as bfs_module
import source.domain.solver.dfs as dfs_module
import source.domain.solver.ucs as ucs_module
from source.application.engine.shuffle import deal_by_game_number
from source.domain.model.state import State
from source.domain.solver.astar import AStarAlgorithm
from source.domain.solver.bfs import BFSAlgorithm
from source.domain.solver.dfs import DFSAlgorithm
from source.domain.solver.ucs import UCSAlgorithm
from source.domain.solver.utils.heuristics import combined_heuristic

ALL_ALGOS = ("BFS", "DFS", "UCS", "A*")


class ExpansionLimitReached(RuntimeError):
    """Raised when expansion counter reaches configured limit."""


class TimeoutReached(RuntimeError):
    """Raised when elapsed time reaches configured timeout."""


@dataclass(frozen=True)
class RunRow:
    algorithm: str
    deal: int
    trial: int
    elapsed_s: float
    elapsed_ms: float
    expanded_nodes: int
    generated_nodes: int
    peak_memory_mb: float
    solution_found: bool
    stop_reason: str


def _parse_csv_list(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


def _parse_algorithms(raw: str) -> list[str]:
    algorithms = _parse_csv_list(raw)
    if not algorithms:
        raise ValueError("--algorithms must contain at least one value")
    unknown = [name for name in algorithms if name not in ALL_ALGOS]
    if unknown:
        raise ValueError(
            f"Unknown algorithm(s): {unknown}. Allowed: {', '.join(ALL_ALGOS)}"
        )
    return algorithms


def _parse_deals(raw: str) -> list[int]:
    text = raw.strip()
    if not text:
        raise ValueError("--deals cannot be empty")

    if "-" in text and "," not in text:
        parts = [p.strip() for p in text.split("-", maxsplit=1)]
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError("--deals range must be in form start-end")
        start = int(parts[0])
        end = int(parts[1])
        if start <= 0 or end <= 0:
            raise ValueError("Deal numbers must be positive")
        if end < start:
            raise ValueError("Deal range end must be >= start")
        return list(range(start, end + 1))

    deals = [int(x) for x in _parse_csv_list(text)]
    if not deals:
        raise ValueError("--deals must contain at least one deal")
    if any(d <= 0 for d in deals):
        raise ValueError("Deal numbers must be positive")
    return deals


def _build_initial_state(deal_number: int) -> State:
    tableau = deal_by_game_number(deal_number)
    return State.from_lists(
        tableau=tableau,
        freecells=[None] * 4,
        foundations=[[] for _ in range(4)],
    )


@contextmanager
def _instrument_get_valid_moves(
    algorithm: str,
    counters: dict[str, int],
    max_expanded_nodes: int,
    timeout_s: float | None,
    started_at: float,
):
    if algorithm == "BFS":
        module = bfs_module
    elif algorithm == "DFS":
        module = dfs_module
    elif algorithm == "UCS":
        module = ucs_module
    elif algorithm == "A*":
        module = astar_module
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    original_get_valid_moves = module.get_valid_moves

    def wrapped_get_valid_moves(state, *args, **kwargs):
        if timeout_s is not None and (perf_counter() - started_at) >= timeout_s:
            raise TimeoutReached()
        if counters["expanded"] >= max_expanded_nodes:
            raise ExpansionLimitReached()

        counters["expanded"] += 1
        moves = original_get_valid_moves(state, *args, **kwargs)
        counters["generated"] += len(moves)
        return moves

    module.get_valid_moves = wrapped_get_valid_moves
    try:
        yield
    finally:
        module.get_valid_moves = original_get_valid_moves


def _run_single(
    *,
    algorithm: str,
    deal: int,
    trial: int,
    timeout_s: float | None,
    max_expanded_nodes: int,
    astar_weight: float,
) -> RunRow:
    counters = {"expanded": 0, "generated": 0}
    started_at = perf_counter()
    stop_reason = "unknown"
    solution_found = False

    tracemalloc.start()
    try:
        initial_state = _build_initial_state(deal)
        with _instrument_get_valid_moves(
            algorithm=algorithm,
            counters=counters,
            max_expanded_nodes=max_expanded_nodes,
            timeout_s=timeout_s,
            started_at=started_at,
        ):
            if algorithm == "BFS":
                solver = BFSAlgorithm(initial_state)
                path = solver.search()
            elif algorithm == "DFS":
                solver = DFSAlgorithm(initial_state)
                path = solver.search()
            elif algorithm == "UCS":
                solver = UCSAlgorithm(
                    initial_state,
                    should_cancel=lambda: False,
                )
                path = solver.search()
            elif algorithm == "A*":
                solver = AStarAlgorithm(
                    initial_state,
                    heuristic_func=combined_heuristic,
                    weight=astar_weight,
                    should_cancel=lambda: False,
                )
                path = solver.search()
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")

            if path is None:
                stop_reason = "frontier_exhausted"
                solution_found = False
            else:
                stop_reason = "solved"
                solution_found = True
    except TimeoutReached:
        stop_reason = "timeout"
        solution_found = False
    except ExpansionLimitReached:
        stop_reason = "max_expanded"
        solution_found = False
    finally:
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

    elapsed_s = perf_counter() - started_at
    return RunRow(
        algorithm=algorithm,
        deal=deal,
        trial=trial,
        elapsed_s=float(elapsed_s),
        elapsed_ms=float(elapsed_s * 1000.0),
        expanded_nodes=int(counters["expanded"]),
        generated_nodes=int(counters["generated"]),
        peak_memory_mb=float(peak_bytes) / (1024.0 * 1024.0),
        solution_found=solution_found,
        stop_reason=stop_reason,
    )


def _summarize_by_algorithm(rows: list[RunRow]) -> dict[str, dict[str, float | int]]:
    summary: dict[str, dict[str, float | int]] = {}
    for algorithm in ALL_ALGOS:
        subset = [r for r in rows if r.algorithm == algorithm]
        if not subset:
            continue
        solved = [r for r in subset if r.solution_found]
        summary[algorithm] = {
            "runs": len(subset),
            "solved": len(solved),
            "timeouts": sum(1 for r in subset if r.stop_reason == "timeout"),
            "max_expanded": sum(1 for r in subset if r.stop_reason == "max_expanded"),
            "median_elapsed_s": sorted(r.elapsed_s for r in subset)[len(subset) // 2],
            "median_peak_memory_mb": sorted(r.peak_memory_mb for r in subset)[
                len(subset) // 2
            ],
            "median_expanded_nodes": sorted(r.expanded_nodes for r in subset)[
                len(subset) // 2
            ],
        }
    return summary


def _write_rows_csv(rows: list[RunRow], path: Path) -> None:
    fieldnames = [
        "algorithm",
        "deal",
        "trial",
        "elapsed_s",
        "elapsed_ms",
        "expanded_nodes",
        "generated_nodes",
        "peak_memory_mb",
        "solution_found",
        "stop_reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def _default_output_dir() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return ROOT / "benchmark_results" / f"algorithm_memory_time_{ts}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark BFS/DFS/UCS/A* for elapsed time, expanded nodes, and peak memory"
    )
    parser.add_argument(
        "--deals",
        type=str,
        default="1-20",
        help="Deal range or list, e.g. 1-20 or 1,2,3,10",
    )
    parser.add_argument(
        "--algorithms",
        type=str,
        default="BFS,DFS,UCS,A*",
        help="Comma-separated list from BFS,DFS,UCS,A*",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=1,
        help="Trials per algorithm/deal",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=8.0,
        help="Per-run timeout in seconds (set <=0 to disable)",
    )
    parser.add_argument(
        "--max-expanded-nodes",
        type=int,
        default=250000,
        help="Per-run expansion cap",
    )
    parser.add_argument(
        "--astar-weight",
        type=float,
        default=5.0,
        help="A* heuristic weight",
    )
    parser.add_argument(
        "--gc-between-runs",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run gc.collect() between runs",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="",
        help="Output directory (default: benchmark_results/algorithm_memory_time_<timestamp>)",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.trials <= 0:
        raise ValueError("--trials must be > 0")
    if args.max_expanded_nodes <= 0:
        raise ValueError("--max-expanded-nodes must be > 0")
    if args.astar_weight <= 0:
        raise ValueError("--astar-weight must be > 0")

    deals = _parse_deals(args.deals)
    algorithms = _parse_algorithms(args.algorithms)
    timeout_s = args.timeout_s if args.timeout_s and args.timeout_s > 0 else None

    output_dir = Path(args.output_dir) if args.output_dir else _default_output_dir()
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    os.environ["UCS_RUNTIME_LOG"] = "0"
    os.environ["ASTAR_RUNTIME_LOG"] = "0"

    rows: list[RunRow] = []
    for deal in deals:
        for algorithm in algorithms:
            for trial in range(1, args.trials + 1):
                if args.gc_between_runs:
                    gc.collect()
                row = _run_single(
                    algorithm=algorithm,
                    deal=deal,
                    trial=trial,
                    timeout_s=timeout_s,
                    max_expanded_nodes=args.max_expanded_nodes,
                    astar_weight=args.astar_weight,
                )
                rows.append(row)
                print(
                    f"{algorithm:>3} deal={deal:>3} trial={trial} "
                    f"elapsed={row.elapsed_s:>7.3f}s expanded={row.expanded_nodes:>7} "
                    f"peak={row.peak_memory_mb:>8.2f}MB stop={row.stop_reason}"
                )

    rows_csv = output_dir / "rows.csv"
    report_json = output_dir / "report.json"
    _write_rows_csv(rows, rows_csv)

    report = {
        "meta": {
            "deals": deals,
            "algorithms": algorithms,
            "trials": args.trials,
            "timeout_s": timeout_s,
            "max_expanded_nodes": args.max_expanded_nodes,
            "astar_weight": args.astar_weight,
            "gc_between_runs": bool(args.gc_between_runs),
        },
        "rows": [asdict(row) for row in rows],
        "summary_by_algorithm": _summarize_by_algorithm(rows),
        "artifacts": {
            "rows_csv": str(rows_csv),
            "report_json": str(report_json),
        },
    }
    report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report["summary_by_algorithm"], indent=2))
    print(f"Wrote: {rows_csv}")
    print(f"Wrote: {report_json}")


if __name__ == "__main__":
    main()