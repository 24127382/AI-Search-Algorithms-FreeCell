"""Benchmark harness for UCS path-cost tuning and A* heuristic comparison.

Usage examples:
    # Pilot (quick)
    c:/Users/mduy/source/repos/AI-Search-Algorithms-FreeCell/.venv/Scripts/python.exe \
        source/application/experiments/benchmark_ucs_astar_tuning.py \
        --start-deal 1 --end-deal 20

    # Full benchmark (deals 1..100)
    c:/Users/mduy/source/repos/AI-Search-Algorithms-FreeCell/.venv/Scripts/python.exe \
        source/application/experiments/benchmark_ucs_astar_tuning.py \
        --start-deal 1 --end-deal 100
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class RunConfig:
    start_deal: int
    end_deal: int
    timeout_seconds: float
    astar_weight: float


def _parse_int_list(raw: str) -> list[int]:
    values = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        values.append(int(part))
    if not values:
        raise ValueError("Expected at least one integer value")
    return values


def _parse_str_list(raw: str) -> list[str]:
    values = [part.strip() for part in raw.split(",") if part.strip()]
    if not values:
        raise ValueError("Expected at least one name")
    return values


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _run_subprocess_json(args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        args,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Subprocess failed with code "
            f"{proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Subprocess did not return valid JSON.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        ) from exc


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.fmean(values))


def _median_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _summarize_ucs_rows(
    rows: list[dict[str, Any]], foundation_costs: list[int]
) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    grouped: dict[int, list[dict[str, Any]]] = {cost: [] for cost in foundation_costs}
    for row in rows:
        grouped[row["foundation_move_cost"]].append(row)

    baseline_cost = foundation_costs[0]
    baseline_rows = grouped[baseline_cost]
    baseline_solved_by_deal = {
        row["deal"]: row
        for row in baseline_rows
        if row["solution_found"] and not row["timed_out"]
    }

    for cost in foundation_costs:
        cost_rows = grouped[cost]
        solved = [r for r in cost_rows if r["solution_found"] and not r["timed_out"]]
        elapsed_ms = [float(r["elapsed_ms"]) for r in solved]
        solution_len = [int(r["solution_length"]) for r in solved]

        common_deals = [
            deal
            for deal in baseline_solved_by_deal
            if deal
            in {
                r["deal"]
                for r in solved
            }
        ]
        speedup_ratios: list[float] = []
        length_deltas: list[int] = []
        solved_by_deal = {r["deal"]: r for r in solved}
        for deal in common_deals:
            base_row = baseline_solved_by_deal[deal]
            candidate_row = solved_by_deal[deal]
            candidate_elapsed = float(candidate_row["elapsed_ms"])
            if candidate_elapsed > 0:
                speedup_ratios.append(float(base_row["elapsed_ms"]) / candidate_elapsed)
            length_deltas.append(
                int(candidate_row["solution_length"]) - int(base_row["solution_length"])
            )

        summary.append(
            {
                "foundation_move_cost": cost,
                "cases": len(cost_rows),
                "solved": len(solved),
                "timeouts": sum(1 for r in cost_rows if r["timed_out"]),
                "unsolved_non_timeout": sum(
                    1
                    for r in cost_rows
                    if (not r["solution_found"]) and (not r["timed_out"])
                ),
                "mean_elapsed_ms_solved": _mean_or_none(elapsed_ms),
                "median_elapsed_ms_solved": _median_or_none(elapsed_ms),
                "mean_solution_length": _mean_or_none([float(v) for v in solution_len]),
                "common_with_baseline": len(common_deals),
                "speedup_vs_baseline_x": _mean_or_none(speedup_ratios),
                "solution_length_delta_vs_baseline": _mean_or_none(
                    [float(v) for v in length_deltas]
                ),
            }
        )

    return summary


def _summarize_astar_rows(rows: list[dict[str, Any]], heuristic_names: list[str]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in heuristic_names}
    for row in rows:
        grouped[row["heuristic"]].append(row)

    baseline_name = "combined_heuristic"
    if baseline_name not in grouped:
        baseline_name = heuristic_names[0]

    baseline_solved_by_deal = {
        row["deal"]: row
        for row in grouped[baseline_name]
        if row["solution_found"] and not row["timed_out"]
    }

    for name in heuristic_names:
        rows_for_h = grouped[name]
        solved = [r for r in rows_for_h if r["solution_found"] and not r["timed_out"]]
        elapsed_ms = [float(r["elapsed_ms"]) for r in solved]
        solution_len = [int(r["solution_length"]) for r in solved]

        solved_by_deal = {r["deal"]: r for r in solved}
        common_deals = [deal for deal in baseline_solved_by_deal if deal in solved_by_deal]
        speedup_ratios: list[float] = []
        length_deltas: list[int] = []
        for deal in common_deals:
            base_row = baseline_solved_by_deal[deal]
            candidate_row = solved_by_deal[deal]
            candidate_elapsed = float(candidate_row["elapsed_ms"])
            if candidate_elapsed > 0:
                speedup_ratios.append(float(base_row["elapsed_ms"]) / candidate_elapsed)
            length_deltas.append(
                int(candidate_row["solution_length"]) - int(base_row["solution_length"])
            )

        summary.append(
            {
                "heuristic": name,
                "cases": len(rows_for_h),
                "solved": len(solved),
                "timeouts": sum(1 for r in rows_for_h if r["timed_out"]),
                "unsolved_non_timeout": sum(
                    1
                    for r in rows_for_h
                    if (not r["solution_found"]) and (not r["timed_out"])
                ),
                "mean_elapsed_ms_solved": _mean_or_none(elapsed_ms),
                "median_elapsed_ms_solved": _median_or_none(elapsed_ms),
                "mean_solution_length": _mean_or_none([float(v) for v in solution_len]),
                "common_with_baseline": len(common_deals),
                "speedup_vs_combined_x": _mean_or_none(speedup_ratios),
                "solution_length_delta_vs_combined": _mean_or_none(
                    [float(v) for v in length_deltas]
                ),
                "admissibility_violation_witnesses": sum(
                    1 for r in solved if r.get("admissibility_witness", False)
                ),
            }
        )

    return summary


def _pick_astar_foundation_cost(ucs_summary: list[dict[str, Any]], fallback: int) -> int:
    candidates = [item for item in ucs_summary if item["solved"] > 0]
    if not candidates:
        return fallback

    def key(item: dict[str, Any]) -> tuple[int, float, float]:
        solved = int(item["solved"])
        speed = float(item["mean_elapsed_ms_solved"] or 1e18)
        length = float(item["mean_solution_length"] or 1e18)
        return (-solved, speed, length)

    best = sorted(candidates, key=key)[0]
    return int(best["foundation_move_cost"])


def _run_driver(args: argparse.Namespace) -> None:
    run_config = RunConfig(
        start_deal=args.start_deal,
        end_deal=args.end_deal,
        timeout_seconds=args.timeout_seconds,
        astar_weight=args.astar_weight,
    )
    foundation_costs = _parse_int_list(args.ucs_foundation_costs)
    heuristic_names = _parse_str_list(args.astar_heuristics)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = ROOT / args.output_dir / f"tuning_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    python_exe = sys.executable
    script_path = Path(__file__).resolve()

    ucs_rows: list[dict[str, Any]] = []
    max_parallel = max(1, int(args.max_parallel_configs))
    with ThreadPoolExecutor(max_workers=max_parallel) as executor:
        futures = {
            executor.submit(
                _run_subprocess_json,
                [
                    python_exe,
                    str(script_path),
                    "--mode",
                    "ucs-config",
                    "--start-deal",
                    str(run_config.start_deal),
                    "--end-deal",
                    str(run_config.end_deal),
                    "--timeout-seconds",
                    str(run_config.timeout_seconds),
                    "--foundation-cost",
                    str(cost),
                ],
            ): cost
            for cost in foundation_costs
        }

        for future in as_completed(futures):
            payload = future.result()
            ucs_rows.extend(payload["rows"])

    ucs_summary = _summarize_ucs_rows(ucs_rows, foundation_costs)
    _write_json(output_dir / "ucs_rows.json", ucs_rows)
    _write_json(output_dir / "ucs_summary.json", ucs_summary)
    _write_csv(output_dir / "ucs_rows.csv", ucs_rows)
    _write_csv(output_dir / "ucs_summary.csv", ucs_summary)

    astar_foundation_cost = (
        args.astar_foundation_cost
        if args.astar_foundation_cost is not None
        else _pick_astar_foundation_cost(ucs_summary, fallback=foundation_costs[0])
    )

    astar_rows: list[dict[str, Any]] = []
    consistency_rows: list[dict[str, Any]] = []
    max_parallel_heuristics = max(1, int(args.max_parallel_heuristics))
    with ThreadPoolExecutor(max_workers=max_parallel_heuristics) as executor:
        futures = {
            executor.submit(
                _run_subprocess_json,
                [
                    python_exe,
                    str(script_path),
                    "--mode",
                    "astar-heuristic",
                    "--start-deal",
                    str(run_config.start_deal),
                    "--end-deal",
                    str(run_config.end_deal),
                    "--timeout-seconds",
                    str(run_config.timeout_seconds),
                    "--astar-weight",
                    str(run_config.astar_weight),
                    "--foundation-cost",
                    str(astar_foundation_cost),
                    "--heuristic-name",
                    heuristic_name,
                    "--consistency-sample-deals",
                    str(args.consistency_sample_deals),
                    "--consistency-max-expansions",
                    str(args.consistency_max_expansions),
                ],
            ): heuristic_name
            for heuristic_name in heuristic_names
        }

        for future in as_completed(futures):
            payload = future.result()
            astar_rows.extend(payload["rows"])
            consistency_rows.extend(payload["consistency"])
    astar_summary = _summarize_astar_rows(astar_rows, heuristic_names)

    _write_json(output_dir / "astar_rows.json", astar_rows)
    _write_json(output_dir / "astar_summary.json", astar_summary)
    _write_json(output_dir / "astar_consistency.json", consistency_rows)
    _write_csv(output_dir / "astar_rows.csv", astar_rows)
    _write_csv(output_dir / "astar_summary.csv", astar_summary)
    _write_csv(output_dir / "astar_consistency.csv", consistency_rows)

    report = {
        "run": {
            "start_deal": run_config.start_deal,
            "end_deal": run_config.end_deal,
            "timeout_seconds": run_config.timeout_seconds,
            "astar_weight": run_config.astar_weight,
            "ucs_foundation_costs": foundation_costs,
            "astar_heuristics": heuristic_names,
        },
        "selection": {
            "astar_foundation_cost": astar_foundation_cost,
        },
        "ucs_summary": ucs_summary,
        "astar_summary": astar_summary,
        "astar_consistency": consistency_rows,
        "artifacts": {
            "output_dir": str(output_dir),
        },
    }
    _write_json(output_dir / "report.json", report)
    print(json.dumps(report, indent=2))


def _run_ucs_config_worker(args: argparse.Namespace) -> None:
    os.environ["UCS_RUNTIME_LOG"] = "0"
    os.environ["ASTAR_RUNTIME_LOG"] = "0"
    os.environ["UCS_FOUNDATION_MOVE_COST"] = str(args.foundation_cost)

    from time import perf_counter

    from source.application.services.game_service import GameService
    from source.domain.solver.ucs import UCSAlgorithm

    rows: list[dict[str, Any]] = []
    for deal in range(args.start_deal, args.end_deal + 1):
        _, state = GameService.build_initial_state(deal)
        started = perf_counter()

        def should_cancel() -> bool:
            return (perf_counter() - started) >= float(args.timeout_seconds)

        solver = UCSAlgorithm(state, should_cancel=should_cancel)
        path = solver.search()
        stats = solver.last_run_stats or {}
        elapsed_ms = float(stats.get("elapsed_ms", (perf_counter() - started) * 1000.0))
        stop_reason = str(stats.get("stop_reason", "unknown"))

        timed_out = stop_reason == "cancelled" and elapsed_ms >= (args.timeout_seconds * 1000.0 * 0.98)
        solution_found = bool(path is not None)

        rows.append(
            {
                "algorithm": "UCS",
                "deal": deal,
                "foundation_move_cost": int(args.foundation_cost),
                "timed_out": timed_out,
                "solution_found": solution_found,
                "elapsed_ms": elapsed_ms,
                "solution_length": int(stats.get("solution_length", 0)),
                "solution_cost": stats.get("solution_cost"),
                "stop_reason": stop_reason,
                "expanded_nodes": int(stats.get("expanded_nodes", 0)),
                "generated_nodes": int(stats.get("generated_nodes", 0)),
                "dominance_pruned": int(stats.get("dominance_pruned", 0)),
            }
        )

    print(json.dumps({"rows": rows}))


def _resolve_heuristic(name: str):
    from source.domain.solver.utils.heuristics import (
        buried_cards,
        combined_heuristic,
        foundation_cost_lower_bound,
        foundation_distance,
        progress_pressure_heuristic,
        zero_heuristic,
    )

    mapping = {
        "zero_heuristic": zero_heuristic,
        "foundation_distance": foundation_distance,
        "buried_cards": buried_cards,
        "combined_heuristic": combined_heuristic,
        "progress_pressure_heuristic": progress_pressure_heuristic,
        "foundation_cost_lower_bound": foundation_cost_lower_bound,
    }
    if name not in mapping:
        raise ValueError(f"Unknown heuristic: {name}")
    return mapping[name]


def _run_astar_heuristic_worker(args: argparse.Namespace) -> None:
    os.environ["UCS_RUNTIME_LOG"] = "0"
    os.environ["ASTAR_RUNTIME_LOG"] = "0"
    os.environ["UCS_FOUNDATION_MOVE_COST"] = str(args.foundation_cost)

    from time import perf_counter

    from source.application.engine.engine import apply_move_with_forced, get_valid_moves
    from source.application.services.game_service import GameService
    from source.domain.solver.astar import AStarAlgorithm
    from source.domain.solver.search_utils.ucs_utils import ucs_move_cost
    from source.domain.solver.utils.utility import state_id

    heuristic_names = [str(args.heuristic_name)]
    rows: list[dict[str, Any]] = []

    for heuristic_name in heuristic_names:
        heuristic = _resolve_heuristic(heuristic_name)
        for deal in range(args.start_deal, args.end_deal + 1):
            _, state = GameService.build_initial_state(deal)
            h0 = int(heuristic(state))
            started = perf_counter()

            def should_cancel() -> bool:
                return (perf_counter() - started) >= float(args.timeout_seconds)

            solver = AStarAlgorithm(
                state,
                heuristic_func=heuristic,
                weight=float(args.astar_weight),
                should_cancel=should_cancel,
            )
            path = solver.search(heuristic)
            stats = solver.last_run_stats or {}
            elapsed_ms = float(
                stats.get("elapsed_ms", (perf_counter() - started) * 1000.0)
            )
            stop_reason = str(stats.get("stop_reason", "unknown"))
            timed_out = stop_reason == "cancelled" and elapsed_ms >= (
                args.timeout_seconds * 1000.0 * 0.98
            )
            solution_found = bool(path is not None)
            solution_cost = stats.get("solution_cost")
            admissibility_witness = bool(
                solution_found
                and solution_cost is not None
                and h0 > float(solution_cost)
            )

            rows.append(
                {
                    "algorithm": "A*",
                    "deal": deal,
                    "foundation_move_cost": int(args.foundation_cost),
                    "heuristic": heuristic_name,
                    "weight": float(args.astar_weight),
                    "timed_out": timed_out,
                    "solution_found": solution_found,
                    "elapsed_ms": elapsed_ms,
                    "solution_length": int(stats.get("solution_length", 0)),
                    "solution_cost": solution_cost,
                    "h0": h0,
                    "admissibility_witness": admissibility_witness,
                    "stop_reason": stop_reason,
                    "expanded_nodes": int(stats.get("expanded_nodes", 0)),
                    "generated_nodes": int(stats.get("generated_nodes", 0)),
                    "reopened_nodes": int(stats.get("reopened_nodes", 0)),
                }
            )

    # Empirical consistency check across sampled local transitions.
    consistency_rows: list[dict[str, Any]] = []
    sample_deals = min(
        int(args.consistency_sample_deals),
        max(0, args.end_deal - args.start_deal + 1),
    )

    for heuristic_name in heuristic_names:
        heuristic = _resolve_heuristic(heuristic_name)
        checks = 0
        violations = 0

        for deal in range(args.start_deal, args.start_deal + sample_deals):
            _, root = GameService.build_initial_state(deal)
            stack = [root]
            seen = {state_id(root)}
            expansions = 0
            max_expansions = int(args.consistency_max_expansions)

            while stack and expansions < max_expansions:
                state = stack.pop()
                expansions += 1
                h_state = float(heuristic(state))

                moves = get_valid_moves(
                    state,
                    prune_safe=True,
                    prune_canonical_redundant=True,
                )
                for move in moves:
                    next_state, forced_moves = apply_move_with_forced(state, move)
                    edge_cost = ucs_move_cost(
                        move, prev_state=state, next_state=next_state
                    )
                    if forced_moves:
                        edge_cost += sum(ucs_move_cost(fm) for fm in forced_moves)

                    h_next = float(heuristic(next_state))
                    checks += 1
                    if h_state > (edge_cost + h_next):
                        violations += 1

                    next_id = state_id(next_state)
                    if next_id not in seen:
                        seen.add(next_id)
                        stack.append(next_state)

        consistency_rows.append(
            {
                "heuristic": heuristic_name,
                "consistency_checks": checks,
                "consistency_violations": violations,
                "consistency_violation_rate": (
                    (violations / checks) if checks else 0.0
                ),
            }
        )

    print(json.dumps({"rows": rows, "consistency": consistency_rows}))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="driver")
    parser.add_argument("--start-deal", type=int, default=1)
    parser.add_argument("--end-deal", type=int, default=100)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--astar-weight", type=float, default=5.0)

    parser.add_argument(
        "--ucs-foundation-costs",
        type=str,
        default="-5,-50,-200,-1000",
    )
    parser.add_argument(
        "--astar-heuristics",
        type=str,
        default=(
            "zero_heuristic,foundation_distance,buried_cards,"
            "combined_heuristic,progress_pressure_heuristic,"
            "foundation_cost_lower_bound"
        ),
    )
    parser.add_argument("--foundation-cost", type=int, default=-1000)
    parser.add_argument("--astar-foundation-cost", type=int, default=None)
    parser.add_argument("--heuristic-name", type=str, default="combined_heuristic")

    parser.add_argument("--consistency-sample-deals", type=int, default=20)
    parser.add_argument("--consistency-max-expansions", type=int, default=150)

    parser.add_argument(
        "--output-dir",
        type=str,
        default="benchmark_results",
    )
    parser.add_argument("--max-parallel-configs", type=int, default=3)
    parser.add_argument("--max-parallel-heuristics", type=int, default=3)
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.mode == "driver":
        _run_driver(args)
        return

    if args.mode == "ucs-config":
        _run_ucs_config_worker(args)
        return

    if args.mode == "astar-heuristic":
        _run_astar_heuristic_worker(args)
        return

    raise ValueError(f"Unknown mode: {args.mode}")


if __name__ == "__main__":
    main()
