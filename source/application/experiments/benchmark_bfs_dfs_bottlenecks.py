"""Benchmark BFS bottlenecks and DFS instability.

This script runs three stages:
1) BFS speed benchmark (expanded nodes/s, frontier growth/s).
2) BFS memory benchmark (peak RSS growth and bytes-per-visited-node estimate).
3) DFS instability benchmark (first-solution latency and solution-length spread).

It then combines stage (1) and (2) to forecast BFS time-to-memory-overflow.
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import math
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class RunConfig:
    start_deal: int
    end_deal: int
    bfs_timeout_seconds: float
    bfs_node_cap: int
    dfs_timeout_seconds: float
    memory_sample_count: int
    memory_poll_ms: int


def _safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.fmean(values))


def _safe_median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def _safe_quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    idx = (len(ordered) - 1) * q
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return float(ordered[lo])
    ratio = idx - lo
    return float(ordered[lo] * (1.0 - ratio) + ordered[hi] * ratio)


def _safe_cv(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean_val = statistics.fmean(values)
    if mean_val == 0:
        return None
    return float(statistics.stdev(values) / mean_val)


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


def _collect_deals(config: RunConfig) -> list[int]:
    return list(range(config.start_deal, config.end_deal + 1))


def _summarize_bfs_speed(rows: list[dict[str, Any]]) -> dict[str, Any]:
    expanded_rates = [float(row["expanded_nodes_per_sec"]) for row in rows]
    frontier_rates = [float(row["frontier_growth_per_sec"]) for row in rows]
    visited_rates = [float(row["visited_growth_per_sec"]) for row in rows]

    bottleneck_rows = [row for row in rows if row["stop_reason"] != "solved"]
    reference_rows = bottleneck_rows if bottleneck_rows else rows

    ref_expanded_rates = [float(row["expanded_nodes_per_sec"]) for row in reference_rows]
    ref_frontier_rates = [float(row["frontier_growth_per_sec"]) for row in reference_rows]

    return {
        "cases": len(rows),
        "bottleneck_cases": len(bottleneck_rows),
        "solved_cases": sum(1 for row in rows if row["solution_found"]),
        "mean_expanded_nodes_per_sec": _safe_mean(expanded_rates),
        "median_expanded_nodes_per_sec": _safe_median(expanded_rates),
        "mean_frontier_growth_per_sec": _safe_mean(frontier_rates),
        "median_frontier_growth_per_sec": _safe_median(frontier_rates),
        "mean_visited_growth_per_sec": _safe_mean(visited_rates),
        "median_visited_growth_per_sec": _safe_median(visited_rates),
        "reference_expanded_nodes_per_sec": _safe_median(ref_expanded_rates),
        "reference_frontier_growth_per_sec": _safe_median(ref_frontier_rates),
    }


def _summarize_bfs_memory(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bytes_per_node = [
        float(row["bytes_per_peak_visited_node"])
        for row in rows
        if row["bytes_per_peak_visited_node"] is not None
    ]
    peak_heap_deltas_mb = [
        float(row["peak_python_heap_delta_bytes"]) / (1024.0 * 1024.0)
        for row in rows
    ]

    return {
        "cases": len(rows),
        "mean_peak_python_heap_delta_mb": _safe_mean(peak_heap_deltas_mb),
        "median_peak_python_heap_delta_mb": _safe_median(peak_heap_deltas_mb),
        "mean_bytes_per_peak_visited_node": _safe_mean(bytes_per_node),
        "median_bytes_per_peak_visited_node": _safe_median(bytes_per_node),
        "p90_bytes_per_peak_visited_node": _safe_quantile(bytes_per_node, 0.9),
    }


def _format_seconds(seconds: float | None) -> str:
    if seconds is None or not math.isfinite(seconds):
        return "n/a"
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds / 60.0:.1f}m"
    return f"{seconds / 3600.0:.2f}h"


def _forecast_bfs_overflow(
    bfs_speed_summary: dict[str, Any],
    bfs_memory_summary: dict[str, Any],
    available_memory_bytes: int,
) -> dict[str, Any]:
    expanded_rate = bfs_speed_summary.get("reference_expanded_nodes_per_sec")
    frontier_rate = bfs_speed_summary.get("reference_frontier_growth_per_sec")
    bytes_per_node = bfs_memory_summary.get("median_bytes_per_peak_visited_node")

    if (
        expanded_rate is None
        or frontier_rate is None
        or bytes_per_node is None
        or expanded_rate <= 0
        or frontier_rate < 0
        or bytes_per_node <= 0
    ):
        return {
            "available_memory_bytes": available_memory_bytes,
            "visited_growth_per_sec": None,
            "memory_growth_bytes_per_sec": None,
            "memory_growth_mb_per_sec": None,
            "predicted_overflow_seconds_raw": None,
            "predicted_overflow_seconds_70pct_headroom": None,
            "predicted_overflow_human_raw": "n/a",
            "predicted_overflow_human_70pct_headroom": "n/a",
        }

    visited_growth_per_sec = float(expanded_rate) + float(frontier_rate)
    memory_growth_bytes_per_sec = visited_growth_per_sec * float(bytes_per_node)
    if memory_growth_bytes_per_sec <= 0:
        return {
            "available_memory_bytes": available_memory_bytes,
            "visited_growth_per_sec": visited_growth_per_sec,
            "memory_growth_bytes_per_sec": memory_growth_bytes_per_sec,
            "memory_growth_mb_per_sec": 0.0,
            "predicted_overflow_seconds_raw": None,
            "predicted_overflow_seconds_70pct_headroom": None,
            "predicted_overflow_human_raw": "n/a",
            "predicted_overflow_human_70pct_headroom": "n/a",
        }

    raw_seconds = available_memory_bytes / memory_growth_bytes_per_sec
    conservative_seconds = (available_memory_bytes * 0.7) / memory_growth_bytes_per_sec

    return {
        "available_memory_bytes": int(available_memory_bytes),
        "visited_growth_per_sec": visited_growth_per_sec,
        "memory_growth_bytes_per_sec": memory_growth_bytes_per_sec,
        "memory_growth_mb_per_sec": memory_growth_bytes_per_sec / (1024.0 * 1024.0),
        "predicted_overflow_seconds_raw": raw_seconds,
        "predicted_overflow_seconds_70pct_headroom": conservative_seconds,
        "predicted_overflow_human_raw": _format_seconds(raw_seconds),
        "predicted_overflow_human_70pct_headroom": _format_seconds(
            conservative_seconds
        ),
    }


def _summarize_dfs_instability(rows: list[dict[str, Any]]) -> dict[str, Any]:
    solved_rows = [row for row in rows if row["solution_found"]]
    solved_lengths = [float(row["solution_length"]) for row in solved_rows]
    solved_times_ms = [float(row["elapsed_ms"]) for row in solved_rows]

    updates_per_hour = [
        3600000.0 / time_ms for time_ms in solved_times_ms if time_ms > 0
    ]

    return {
        "cases": len(rows),
        "solved_cases": len(solved_rows),
        "unsolved_cases": len(rows) - len(solved_rows),
        "solved_ratio": (len(solved_rows) / len(rows)) if rows else 0.0,
        "solution_length_mean": _safe_mean(solved_lengths),
        "solution_length_median": _safe_median(solved_lengths),
        "solution_length_cv": _safe_cv(solved_lengths),
        "solution_length_p10": _safe_quantile(solved_lengths, 0.1),
        "solution_length_p90": _safe_quantile(solved_lengths, 0.9),
        "first_solution_ms_mean": _safe_mean(solved_times_ms),
        "first_solution_ms_median": _safe_median(solved_times_ms),
        "first_solution_ms_cv": _safe_cv(solved_times_ms),
        "first_solution_ms_p10": _safe_quantile(solved_times_ms, 0.1),
        "first_solution_ms_p90": _safe_quantile(solved_times_ms, 0.9),
        "updates_per_hour_mean": _safe_mean(updates_per_hour),
        "updates_per_hour_median": _safe_median(updates_per_hour),
        "updates_per_hour_p10": _safe_quantile(updates_per_hour, 0.1),
        "updates_per_hour_p90": _safe_quantile(updates_per_hour, 0.9),
    }


def _get_process_rss_bytes() -> int:
    try:
        import psutil  # type: ignore

        return int(psutil.Process().memory_info().rss)
    except Exception:
        pass

    if sys.platform.startswith("win"):
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
        process = ctypes.windll.kernel32.GetCurrentProcess()
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(
            process,
            ctypes.byref(counters),
            counters.cb,
        )
        if ok:
            return int(counters.WorkingSetSize)

    return 0


def _get_available_memory_bytes() -> int:
    try:
        import psutil  # type: ignore

        return int(psutil.virtual_memory().available)
    except Exception:
        pass

    if sys.platform.startswith("win"):
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.ullAvailPhys)

    return 0


def _run_bfs_speed_worker(args: argparse.Namespace) -> None:
    from source.application.services.game_service import GameService
    from source.domain.solver.bfs import BFSAlgorithm
    from source.domain.solver.search_utils.search_profile import BFSProfile

    rows: list[dict[str, Any]] = []
    deals = range(args.start_deal, args.end_deal + 1)
    profile = BFSProfile(
        runtime_log_enabled=False,
        hard_time_cap_ms=max(1.0, float(args.bfs_timeout_seconds) * 1000.0),
        max_expanded_nodes=max(1, int(args.bfs_node_cap)),
    )

    for deal in deals:
        _, state = GameService.build_initial_state(deal)
        solver = BFSAlgorithm(state, profile=profile)
        path = solver.search()
        stats = solver.last_run_stats or {}

        elapsed_ms = float(stats.get("elapsed_ms", 0.0))
        elapsed_sec = max(elapsed_ms / 1000.0, 1e-9)
        expanded_nodes = int(stats.get("expanded_nodes", 0))
        final_frontier = int(stats.get("final_frontier_size", 0))
        final_visited = int(stats.get("final_visited_size", 0))

        rows.append(
            {
                "algorithm": "BFS",
                "deal": int(deal),
                "elapsed_ms": elapsed_ms,
                "stop_reason": str(stats.get("stop_reason", "unknown")),
                "solution_found": bool(path is not None),
                "solution_length": int(stats.get("solution_length", 0)),
                "expanded_nodes": expanded_nodes,
                "generated_nodes": int(stats.get("generated_nodes", 0)),
                "peak_frontier_size": int(stats.get("peak_frontier_size", 0)),
                "peak_visited_size": int(stats.get("peak_visited_size", 0)),
                "final_frontier_size": final_frontier,
                "final_visited_size": final_visited,
                "expanded_nodes_per_sec": expanded_nodes / elapsed_sec,
                "frontier_growth_per_sec": final_frontier / elapsed_sec,
                "visited_growth_per_sec": final_visited / elapsed_sec,
            }
        )

    print(json.dumps({"rows": rows}))


def _run_bfs_memory_worker(args: argparse.Namespace) -> None:
    import tracemalloc

    from source.application.services.game_service import GameService
    from source.domain.solver.bfs import BFSAlgorithm
    from source.domain.solver.search_utils.search_profile import BFSProfile

    gc.collect()
    tracemalloc.start()
    heap_start_current, heap_start_peak = tracemalloc.get_traced_memory()

    _, state = GameService.build_initial_state(int(args.deal))
    profile = BFSProfile(
        runtime_log_enabled=False,
        hard_time_cap_ms=max(1.0, float(args.bfs_timeout_seconds) * 1000.0),
        max_expanded_nodes=max(1, int(args.bfs_node_cap)),
    )
    solver = BFSAlgorithm(state, profile=profile)

    outcome: dict[str, Any] = {"path": None, "error": None}

    def _run_solver() -> None:
        try:
            outcome["path"] = solver.search()
        except Exception as exc:  # pragma: no cover - benchmark guard
            outcome["error"] = str(exc)

    thread = threading.Thread(target=_run_solver, daemon=True)
    thread.start()

    heap_peak = heap_start_peak
    poll_seconds = max(0.005, float(args.memory_poll_ms) / 1000.0)
    while thread.is_alive():
        _, observed_peak = tracemalloc.get_traced_memory()
        heap_peak = max(heap_peak, observed_peak)
        time.sleep(poll_seconds)
    thread.join()

    heap_end_current, heap_end_peak = tracemalloc.get_traced_memory()
    heap_peak = max(heap_peak, heap_end_peak)
    tracemalloc.stop()

    stats = solver.last_run_stats or {}

    if outcome["error"] is not None:
        raise RuntimeError(f"Memory worker failed for deal {args.deal}: {outcome['error']}")

    peak_visited = int(stats.get("peak_visited_size", 0))
    peak_delta = max(0, int(heap_peak - heap_start_current))
    bytes_per_peak_visited_node = (
        (peak_delta / max(peak_visited, 1)) if peak_visited > 0 else None
    )

    row = {
        "deal": int(args.deal),
        "stop_reason": str(stats.get("stop_reason", "unknown")),
        "solution_found": bool(outcome["path"] is not None),
        "elapsed_ms": float(stats.get("elapsed_ms", 0.0)),
        "peak_visited_size": peak_visited,
        "peak_frontier_size": int(stats.get("peak_frontier_size", 0)),
        "python_heap_start_current_bytes": int(heap_start_current),
        "python_heap_end_current_bytes": int(heap_end_current),
        "python_heap_peak_bytes": int(heap_peak),
        "peak_python_heap_delta_bytes": peak_delta,
        "bytes_per_peak_visited_node": bytes_per_peak_visited_node,
    }

    print(json.dumps({"row": row}))


def _run_dfs_instability_worker(args: argparse.Namespace) -> None:
    from source.application.services.game_service import GameService
    from source.domain.solver.dfs import DFSAlgorithm
    from source.domain.solver.search_utils.search_profile import DFSProfile

    rows: list[dict[str, Any]] = []
    deals = range(args.start_deal, args.end_deal + 1)
    profile = DFSProfile(
        runtime_log_enabled=False,
        hard_time_cap_ms=max(1.0, float(args.dfs_timeout_seconds) * 1000.0),
    )

    for deal in deals:
        _, state = GameService.build_initial_state(deal)
        solver = DFSAlgorithm(state, profile=profile, runtime_log_enabled=False)
        path = solver.search()
        stats = solver.last_run_stats or {}

        rows.append(
            {
                "algorithm": "DFS",
                "deal": int(deal),
                "elapsed_ms": float(stats.get("elapsed_ms", 0.0)),
                "stop_reason": str(stats.get("stop_reason", "unknown")),
                "solution_found": bool(path is not None),
                "solution_length": int(stats.get("solution_length", 0)),
                "expanded_nodes": int(stats.get("expanded_nodes", 0)),
                "generated_nodes": int(stats.get("generated_nodes", 0)),
                "peak_frontier_size": int(stats.get("peak_frontier_size", 0)),
                "peak_visited_size": int(stats.get("peak_visited_size", 0)),
            }
        )

    print(json.dumps({"rows": rows}))


def _run_driver(args: argparse.Namespace) -> None:
    config = RunConfig(
        start_deal=int(args.start_deal),
        end_deal=int(args.end_deal),
        bfs_timeout_seconds=float(args.bfs_timeout_seconds),
        bfs_node_cap=int(args.bfs_node_cap),
        dfs_timeout_seconds=float(args.dfs_timeout_seconds),
        memory_sample_count=int(args.memory_sample_count),
        memory_poll_ms=int(args.memory_poll_ms),
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / args.output_dir / f"bfs_dfs_bottlenecks_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    python_exe = sys.executable
    script_path = Path(__file__).resolve()

    bfs_speed_payload = _run_subprocess_json(
        [
            python_exe,
            str(script_path),
            "--mode",
            "bfs-speed-worker",
            "--start-deal",
            str(config.start_deal),
            "--end-deal",
            str(config.end_deal),
            "--bfs-timeout-seconds",
            str(config.bfs_timeout_seconds),
            "--bfs-node-cap",
            str(config.bfs_node_cap),
        ]
    )
    bfs_speed_rows = list(bfs_speed_payload["rows"])
    bfs_speed_summary = _summarize_bfs_speed(bfs_speed_rows)

    memory_candidates = sorted(
        bfs_speed_rows,
        key=lambda row: (
            int(row.get("final_frontier_size", 0)),
            int(row.get("expanded_nodes", 0)),
        ),
        reverse=True,
    )
    memory_deals = [
        int(row["deal"])
        for row in memory_candidates[: max(1, config.memory_sample_count)]
    ]

    bfs_memory_rows: list[dict[str, Any]] = []
    for deal in memory_deals:
        payload = _run_subprocess_json(
            [
                python_exe,
                str(script_path),
                "--mode",
                "bfs-memory-worker",
                "--deal",
                str(deal),
                "--bfs-timeout-seconds",
                str(config.bfs_timeout_seconds),
                "--bfs-node-cap",
                str(config.bfs_node_cap),
                "--memory-poll-ms",
                str(config.memory_poll_ms),
            ]
        )
        bfs_memory_rows.append(dict(payload["row"]))

    bfs_memory_summary = _summarize_bfs_memory(bfs_memory_rows)

    available_memory_bytes = _get_available_memory_bytes()
    overflow_forecast = _forecast_bfs_overflow(
        bfs_speed_summary,
        bfs_memory_summary,
        available_memory_bytes=available_memory_bytes,
    )

    dfs_payload = _run_subprocess_json(
        [
            python_exe,
            str(script_path),
            "--mode",
            "dfs-instability-worker",
            "--start-deal",
            str(config.start_deal),
            "--end-deal",
            str(config.end_deal),
            "--dfs-timeout-seconds",
            str(config.dfs_timeout_seconds),
        ]
    )
    dfs_rows = list(dfs_payload["rows"])
    dfs_instability_summary = _summarize_dfs_instability(dfs_rows)

    report = {
        "run": {
            "start_deal": config.start_deal,
            "end_deal": config.end_deal,
            "bfs_timeout_seconds": config.bfs_timeout_seconds,
            "bfs_node_cap": config.bfs_node_cap,
            "dfs_timeout_seconds": config.dfs_timeout_seconds,
            "memory_sample_count": config.memory_sample_count,
            "memory_poll_ms": config.memory_poll_ms,
        },
        "bfs_speed_summary": bfs_speed_summary,
        "bfs_memory_summary": bfs_memory_summary,
        "bfs_memory_overflow_forecast": overflow_forecast,
        "dfs_instability_summary": dfs_instability_summary,
        "memory_deals": memory_deals,
        "artifacts": {
            "output_dir": str(out_dir),
        },
    }

    _write_json(out_dir / "bfs_speed_rows.json", bfs_speed_rows)
    _write_csv(out_dir / "bfs_speed_rows.csv", bfs_speed_rows)

    _write_json(out_dir / "bfs_memory_rows.json", bfs_memory_rows)
    _write_csv(out_dir / "bfs_memory_rows.csv", bfs_memory_rows)

    _write_json(out_dir / "dfs_rows.json", dfs_rows)
    _write_csv(out_dir / "dfs_rows.csv", dfs_rows)

    _write_json(out_dir / "report.json", report)
    print(json.dumps(report, indent=2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="driver")
    parser.add_argument("--start-deal", type=int, default=1)
    parser.add_argument("--end-deal", type=int, default=30)

    parser.add_argument("--bfs-timeout-seconds", type=float, default=8.0)
    parser.add_argument("--bfs-node-cap", type=int, default=1000000)

    parser.add_argument("--dfs-timeout-seconds", type=float, default=12.0)

    parser.add_argument("--memory-sample-count", type=int, default=8)
    parser.add_argument("--memory-poll-ms", type=int, default=20)
    parser.add_argument("--deal", type=int, default=1)

    parser.add_argument("--output-dir", type=str, default="benchmark_results")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.mode == "driver":
        _run_driver(args)
        return
    if args.mode == "bfs-speed-worker":
        _run_bfs_speed_worker(args)
        return
    if args.mode == "bfs-memory-worker":
        _run_bfs_memory_worker(args)
        return
    if args.mode == "dfs-instability-worker":
        _run_dfs_instability_worker(args)
        return

    raise ValueError(f"Unknown mode: {args.mode}")


if __name__ == "__main__":
    main()
