"""Grouped optimization ablation benchmark for FreeCell solvers.

This benchmark focuses on practical, switchable optimization groups:
1) State-keying modes (packed board_code vs unpacked tuple vs Zobrist hash)
2) UCS rule/engine ablation (canonical-prune and forced-foundation closure)
3) UCS candidate move sorting (off/on)
4) A* arena compaction (off/on)

Outputs a single JSON report to benchmark_results/optimization_groups_<timestamp>/report.json
and prints the same report to stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import engine first to avoid known service/solver circular-import ordering issues.
import source.application.engine.engine as engine_module
import source.domain.solver.astar as astar_module
import source.domain.solver.bfs as bfs_module
import source.domain.solver.dfs as dfs_module
import source.domain.solver.search_utils.ucs_utils as ucs_utils_module
import source.domain.solver.ucs as ucs_module
import source.domain.solver.utils.utility as utility_module
from source.application.services.game_service import GameService
from source.domain.model.state import State
from source.domain.solver.astar import AStarAlgorithm
from source.domain.solver.bfs import BFSAlgorithm
from source.domain.solver.dfs import DFSAlgorithm
from source.domain.solver.search_utils.search_profile import AStarProfile, UCSProfile
from source.domain.solver.ucs import UCSAlgorithm
from source.domain.solver.utils.heuristics import combined_heuristic
from source.domain.solver.utils.zobrist import zobrist_hash_state

PACKED_MODE = "packed"
UNPACKED_MODE = "unpacked"
ZOBRIST_MODE = "zobrist"


@dataclass(frozen=True)
class RunOutcome:
    algorithm: str
    deal: int
    config: str
    solved: bool
    timed_out: bool
    elapsed_ms: float
    expanded_nodes: int
    generated_nodes: int
    solution_length: int
    stop_reason: str


@dataclass
class _Counter:
    expanded: int = 0
    generated: int = 0


@contextmanager
def _patch_state_key_mode(mode: str):
    """Patch canonical key functions used by BFS/UCS/A* for key-mode benchmark."""
    original_utility_state_id = utility_module.state_id
    original_utility_state_key = utility_module.state_key
    original_ucs_state_id = ucs_module.state_id
    original_astar_state_id = astar_module.state_id
    original_bfs_state_key = bfs_module.state_key
    original_dfs_state_key = getattr(dfs_module, "state_key", None)
    original_state_hash = State.__hash__

    if mode == PACKED_MODE:
        selected_state_id = lambda state: state.board_code
        selected_state_key = lambda state: state.board_code
        selected_hash = lambda state: hash(state.board_code)
    elif mode == UNPACKED_MODE:
        selected_state_id = lambda state: (state.tableau, state.freecells, state.foundations)
        selected_state_key = lambda state: (state.tableau, state.freecells, state.foundations)
        selected_hash = lambda state: hash((state.tableau, state.freecells, state.foundations))
    elif mode == ZOBRIST_MODE:
        selected_state_id = lambda state: int(zobrist_hash_state(state))
        selected_state_key = lambda state: int(zobrist_hash_state(state))
        selected_hash = lambda state: int(zobrist_hash_state(state))
    else:
        raise ValueError(f"Unsupported key mode: {mode}")

    utility_module.state_id = selected_state_id
    utility_module.state_key = selected_state_key
    ucs_module.state_id = selected_state_id
    astar_module.state_id = selected_state_id
    bfs_module.state_key = selected_state_key
    if hasattr(dfs_module, "state_key"):
        dfs_module.state_key = selected_state_key
    State.__hash__ = selected_hash

    try:
        yield
    finally:
        utility_module.state_id = original_utility_state_id
        utility_module.state_key = original_utility_state_key
        ucs_module.state_id = original_ucs_state_id
        astar_module.state_id = original_astar_state_id
        bfs_module.state_key = original_bfs_state_key
        if original_dfs_state_key is not None and hasattr(dfs_module, "state_key"):
            dfs_module.state_key = original_dfs_state_key
        State.__hash__ = original_state_hash


@contextmanager
def _instrument_expansion_cap(
    algorithm: str,
    max_expand: int,
    timeout_s: float,
    started_at: float,
    counter: _Counter,
):
    """Count expansions/generations by patching solver-local get_valid_moves import."""
    module = {
        "BFS": bfs_module,
        "DFS": dfs_module,
        "UCS": ucs_module,
        "A*": astar_module,
    }[algorithm]

    original_get_valid_moves = module.get_valid_moves

    class _ExpandCap(Exception):
        pass

    class _Timeout(Exception):
        pass

    def wrapped_get_valid_moves(state, *args, **kwargs):
        elapsed = perf_counter() - started_at
        if elapsed >= timeout_s:
            raise _Timeout()
        if counter.expanded >= max_expand:
            raise _ExpandCap()

        counter.expanded += 1
        moves = original_get_valid_moves(state, *args, **kwargs)
        counter.generated += len(moves)
        return moves

    module.get_valid_moves = wrapped_get_valid_moves
    try:
        yield _ExpandCap, _Timeout
    finally:
        module.get_valid_moves = original_get_valid_moves


@contextmanager
def _patch_ucs_rule_engine(
    canonical_prune_enabled: bool,
    forced_closure_enabled: bool,
):
    """Patch UCS hooks to isolate rule/engine optimization impact."""
    original_get_valid_moves = ucs_module.get_valid_moves
    original_apply_move_with_forced = ucs_module.apply_move_with_forced

    def wrapped_get_valid_moves(state, *args, **kwargs):
        kwargs["prune_canonical_redundant"] = canonical_prune_enabled
        return original_get_valid_moves(state, *args, **kwargs)

    def wrapped_apply_move_with_forced(state, move):
        if forced_closure_enabled:
            return original_apply_move_with_forced(state, move)
        next_state = engine_module.apply_move(state, move, collapse_forced=False)
        return next_state, ()

    ucs_module.get_valid_moves = wrapped_get_valid_moves
    ucs_module.apply_move_with_forced = wrapped_apply_move_with_forced
    try:
        yield
    finally:
        ucs_module.get_valid_moves = original_get_valid_moves
        ucs_module.apply_move_with_forced = original_apply_move_with_forced


def _safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.fmean(values))


def _timed_out_from_stats(stop_reason: str, elapsed_ms: float, timeout_s: float) -> bool:
    if stop_reason == "hard_time_cap":
        return True
    if stop_reason == "cancelled" and elapsed_ms >= timeout_s * 1000.0 * 0.98:
        return True
    return False


def _build_state_for_deal(deal: int) -> State:
    _, state = GameService.build_initial_state(int(deal))
    return state


def _run_solver_single(
    algorithm: str,
    deal: int,
    timeout_s: float,
    config_name: str,
    ucs_profile: UCSProfile | None = None,
    astar_profile: AStarProfile | None = None,
) -> RunOutcome:
    state = _build_state_for_deal(deal)
    started_at = perf_counter()

    def should_cancel() -> bool:
        return (perf_counter() - started_at) >= float(timeout_s)

    if algorithm == "BFS":
        solver = BFSAlgorithm(state, should_cancel=should_cancel)
        path = solver.search()
        stats = solver.last_run_stats or {}
    elif algorithm == "DFS":
        solver = DFSAlgorithm(state, should_cancel=should_cancel)
        path = solver.search()
        stats = solver.last_run_stats or {}
    elif algorithm == "UCS":
        solver = UCSAlgorithm(state, should_cancel=should_cancel, profile=ucs_profile)
        path = solver.search()
        stats = solver.last_run_stats or {}
    elif algorithm == "A*":
        solver = AStarAlgorithm(
            state,
            heuristic_func=combined_heuristic,
            weight=5.0,
            should_cancel=should_cancel,
            profile=astar_profile,
        )
        path = solver.search(combined_heuristic)
        stats = solver.last_run_stats or {}
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    elapsed_ms = float(stats.get("elapsed_ms", (perf_counter() - started_at) * 1000.0))
    stop_reason = str(stats.get("stop_reason", "unknown"))

    return RunOutcome(
        algorithm=algorithm,
        deal=int(deal),
        config=config_name,
        solved=bool(path is not None),
        timed_out=_timed_out_from_stats(stop_reason, elapsed_ms, timeout_s),
        elapsed_ms=elapsed_ms,
        expanded_nodes=int(stats.get("expanded_nodes", 0)),
        generated_nodes=int(stats.get("generated_nodes", 0)),
        solution_length=int(stats.get("solution_length", 0)),
        stop_reason=stop_reason,
    )


def _summarize_outcomes(outcomes: list[RunOutcome]) -> dict[str, Any]:
    solved = [o for o in outcomes if o.solved and not o.timed_out]
    elapsed_all = [o.elapsed_ms for o in outcomes]
    elapsed_solved = [o.elapsed_ms for o in solved]
    expanded_all = [float(o.expanded_nodes) for o in outcomes]
    generated_all = [float(o.generated_nodes) for o in outcomes]
    expanded_solved = [float(o.expanded_nodes) for o in solved]
    generated_solved = [float(o.generated_nodes) for o in solved]
    solution_len_solved = [float(o.solution_length) for o in solved]

    return {
        "cases": len(outcomes),
        "solved": len(solved),
        "timed_out": sum(1 for o in outcomes if o.timed_out),
        "mean_elapsed_ms_all": _safe_mean(elapsed_all),
        "mean_elapsed_ms_solved": _safe_mean(elapsed_solved),
        "mean_expanded_nodes_all": _safe_mean(expanded_all),
        "mean_generated_nodes_all": _safe_mean(generated_all),
        "mean_expanded_nodes_solved": _safe_mean(expanded_solved),
        "mean_generated_nodes_solved": _safe_mean(generated_solved),
        "mean_solution_length_solved": _safe_mean(solution_len_solved),
    }


def _delta_vs_baseline(
    summary_by_config: dict[str, dict[str, Any]],
    baseline_config: str,
) -> dict[str, dict[str, float | None]]:
    baseline = summary_by_config[baseline_config]
    baseline_elapsed_all = baseline.get("mean_elapsed_ms_all")
    baseline_elapsed = baseline.get("mean_elapsed_ms_solved")
    baseline_generated_all = baseline.get("mean_generated_nodes_all")
    baseline_generated = baseline.get("mean_generated_nodes_solved")
    baseline_expanded_all = baseline.get("mean_expanded_nodes_all")
    baseline_expanded = baseline.get("mean_expanded_nodes_solved")

    deltas: dict[str, dict[str, float | None]] = {}
    for name, item in summary_by_config.items():
        elapsed_all = item.get("mean_elapsed_ms_all")
        elapsed = item.get("mean_elapsed_ms_solved")
        generated_all = item.get("mean_generated_nodes_all")
        generated = item.get("mean_generated_nodes_solved")
        expanded_all = item.get("mean_expanded_nodes_all")
        expanded = item.get("mean_expanded_nodes_solved")

        elapsed_improve_pct_all = None
        if baseline_elapsed_all and elapsed_all:
            elapsed_improve_pct_all = (
                (baseline_elapsed_all - elapsed_all) / baseline_elapsed_all * 100.0
            )

        elapsed_improve_pct = None
        if baseline_elapsed and elapsed:
            elapsed_improve_pct = (baseline_elapsed - elapsed) / baseline_elapsed * 100.0

        generated_reduction_pct_all = None
        if baseline_generated_all and generated_all:
            generated_reduction_pct_all = (
                (baseline_generated_all - generated_all) / baseline_generated_all * 100.0
            )

        generated_reduction_pct = None
        if baseline_generated and generated:
            generated_reduction_pct = (
                (baseline_generated - generated) / baseline_generated * 100.0
            )

        expanded_reduction_pct_all = None
        if baseline_expanded_all and expanded_all:
            expanded_reduction_pct_all = (
                (baseline_expanded_all - expanded_all) / baseline_expanded_all * 100.0
            )

        expanded_reduction_pct = None
        if baseline_expanded and expanded:
            expanded_reduction_pct = (
                (baseline_expanded - expanded) / baseline_expanded * 100.0
            )

        deltas[name] = {
            "elapsed_improve_pct_vs_baseline_all": elapsed_improve_pct_all,
            "elapsed_improve_pct_vs_baseline": elapsed_improve_pct,
            "generated_reduction_pct_vs_baseline_all": generated_reduction_pct_all,
            "generated_reduction_pct_vs_baseline": generated_reduction_pct,
            "expanded_reduction_pct_vs_baseline_all": expanded_reduction_pct_all,
            "expanded_reduction_pct_vs_baseline": expanded_reduction_pct,
        }

    return deltas


def _benchmark_state_key_modes(
    deals: list[int],
    trials: int,
    timeout_s: float,
    max_expand: int,
    algorithms: list[str],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    for algorithm in algorithms:
        for trial in range(1, trials + 1):
            for deal in deals:
                for mode in (PACKED_MODE, UNPACKED_MODE, ZOBRIST_MODE):
                    started_at = perf_counter()
                    counter = _Counter()
                    stop_reason = "unknown"

                    with _patch_state_key_mode(mode):
                        with _instrument_expansion_cap(
                            algorithm=algorithm,
                            max_expand=max_expand,
                            timeout_s=timeout_s,
                            started_at=started_at,
                            counter=counter,
                        ) as (ExpandCap, TimeoutCap):
                            try:
                                outcome = _run_solver_single(
                                    algorithm=algorithm,
                                    deal=deal,
                                    timeout_s=timeout_s,
                                    config_name=mode,
                                )
                                stop_reason = outcome.stop_reason
                                solved = outcome.solved
                                timed_out = outcome.timed_out
                                solution_length = outcome.solution_length
                            except ExpandCap:
                                elapsed_ms = (perf_counter() - started_at) * 1000.0
                                stop_reason = "max_expand"
                                solved = False
                                timed_out = False
                                solution_length = 0
                                rows.append(
                                    {
                                        "group": "state_key_modes",
                                        "algorithm": algorithm,
                                        "deal": deal,
                                        "trial": trial,
                                        "config": mode,
                                        "elapsed_ms": elapsed_ms,
                                        "expanded_nodes": counter.expanded,
                                        "generated_nodes": counter.generated,
                                        "solved": solved,
                                        "timed_out": timed_out,
                                        "solution_length": solution_length,
                                        "stop_reason": stop_reason,
                                    }
                                )
                                continue
                            except TimeoutCap:
                                elapsed_ms = (perf_counter() - started_at) * 1000.0
                                stop_reason = "timeout"
                                solved = False
                                timed_out = True
                                solution_length = 0
                                rows.append(
                                    {
                                        "group": "state_key_modes",
                                        "algorithm": algorithm,
                                        "deal": deal,
                                        "trial": trial,
                                        "config": mode,
                                        "elapsed_ms": elapsed_ms,
                                        "expanded_nodes": counter.expanded,
                                        "generated_nodes": counter.generated,
                                        "solved": solved,
                                        "timed_out": timed_out,
                                        "solution_length": solution_length,
                                        "stop_reason": stop_reason,
                                    }
                                )
                                continue

                    rows.append(
                        {
                            "group": "state_key_modes",
                            "algorithm": algorithm,
                            "deal": deal,
                            "trial": trial,
                            "config": mode,
                            "elapsed_ms": outcome.elapsed_ms,
                            "expanded_nodes": counter.expanded,
                            "generated_nodes": counter.generated,
                            "solved": solved,
                            "timed_out": timed_out,
                            "solution_length": solution_length,
                            "stop_reason": stop_reason,
                        }
                    )

    summary: dict[str, Any] = {}
    for algorithm in algorithms:
        by_cfg: dict[str, list[RunOutcome]] = {m: [] for m in (PACKED_MODE, UNPACKED_MODE, ZOBRIST_MODE)}
        for row in rows:
            if row["algorithm"] != algorithm:
                continue
            by_cfg[row["config"]].append(
                RunOutcome(
                    algorithm=row["algorithm"],
                    deal=row["deal"],
                    config=row["config"],
                    solved=bool(row["solved"]),
                    timed_out=bool(row["timed_out"]),
                    elapsed_ms=float(row["elapsed_ms"]),
                    expanded_nodes=int(row["expanded_nodes"]),
                    generated_nodes=int(row["generated_nodes"]),
                    solution_length=int(row["solution_length"]),
                    stop_reason=str(row["stop_reason"]),
                )
            )

        cfg_summary = {cfg: _summarize_outcomes(outs) for cfg, outs in by_cfg.items()}
        cfg_delta = _delta_vs_baseline(cfg_summary, baseline_config=PACKED_MODE)
        summary[algorithm] = {
            "summary_by_config": cfg_summary,
            "delta_vs_packed": cfg_delta,
        }

    return {
        "rows": rows,
        "summary": summary,
        "meta": {
            "deals": deals,
            "trials": trials,
            "timeout_s": timeout_s,
            "max_expand": max_expand,
            "algorithms": algorithms,
            "note": "Key-mode patch targets state_key/state_id replacement candidates; Zobrist here is full recompute zobrist_hash_state(state).",
        },
    }


def _benchmark_ucs_rule_engine_ablation(
    deals: list[int],
    trials: int,
    timeout_s: float,
) -> dict[str, Any]:
    configs = [
        ("baseline_no_rule_no_engine", False, False),
        ("rule_only_canonical_prune", True, False),
        ("engine_only_forced_closure", False, True),
        ("full_optimized_rule_plus_engine", True, True),
    ]

    rows: list[dict[str, Any]] = []

    for trial in range(1, trials + 1):
        for deal in deals:
            for name, canonical_prune, forced_closure in configs:
                with _patch_ucs_rule_engine(
                    canonical_prune_enabled=canonical_prune,
                    forced_closure_enabled=forced_closure,
                ):
                    outcome = _run_solver_single(
                        algorithm="UCS",
                        deal=deal,
                        timeout_s=timeout_s,
                        config_name=name,
                    )

                rows.append(
                    {
                        "group": "ucs_rule_engine_ablation",
                        "algorithm": "UCS",
                        "deal": deal,
                        "trial": trial,
                        "config": name,
                        "elapsed_ms": outcome.elapsed_ms,
                        "expanded_nodes": outcome.expanded_nodes,
                        "generated_nodes": outcome.generated_nodes,
                        "solved": outcome.solved,
                        "timed_out": outcome.timed_out,
                        "solution_length": outcome.solution_length,
                        "stop_reason": outcome.stop_reason,
                    }
                )

    by_cfg: dict[str, list[RunOutcome]] = {name: [] for name, _, _ in configs}
    for row in rows:
        by_cfg[row["config"]].append(
            RunOutcome(
                algorithm="UCS",
                deal=int(row["deal"]),
                config=row["config"],
                solved=bool(row["solved"]),
                timed_out=bool(row["timed_out"]),
                elapsed_ms=float(row["elapsed_ms"]),
                expanded_nodes=int(row["expanded_nodes"]),
                generated_nodes=int(row["generated_nodes"]),
                solution_length=int(row["solution_length"]),
                stop_reason=str(row["stop_reason"]),
            )
        )

    summary_by_cfg = {cfg: _summarize_outcomes(items) for cfg, items in by_cfg.items()}
    delta = _delta_vs_baseline(summary_by_cfg, baseline_config="baseline_no_rule_no_engine")

    return {
        "rows": rows,
        "summary": {
            "summary_by_config": summary_by_cfg,
            "delta_vs_baseline": delta,
        },
        "meta": {
            "deals": deals,
            "trials": trials,
            "timeout_s": timeout_s,
        },
    }


def _benchmark_ucs_sort_toggle(
    deals: list[int],
    trials: int,
    timeout_s: float,
) -> dict[str, Any]:
    configs = [
        ("sort_off_default", False),
        ("sort_on", True),
    ]

    rows: list[dict[str, Any]] = []
    for trial in range(1, trials + 1):
        for deal in deals:
            for name, sort_flag in configs:
                profile = UCSProfile(sort_candidate_moves=sort_flag)
                outcome = _run_solver_single(
                    algorithm="UCS",
                    deal=deal,
                    timeout_s=timeout_s,
                    config_name=name,
                    ucs_profile=profile,
                )
                rows.append(
                    {
                        "group": "ucs_sort_toggle",
                        "algorithm": "UCS",
                        "deal": deal,
                        "trial": trial,
                        "config": name,
                        "elapsed_ms": outcome.elapsed_ms,
                        "expanded_nodes": outcome.expanded_nodes,
                        "generated_nodes": outcome.generated_nodes,
                        "solved": outcome.solved,
                        "timed_out": outcome.timed_out,
                        "solution_length": outcome.solution_length,
                        "stop_reason": outcome.stop_reason,
                    }
                )

    by_cfg: dict[str, list[RunOutcome]] = {name: [] for name, _ in configs}
    for row in rows:
        by_cfg[row["config"]].append(
            RunOutcome(
                algorithm="UCS",
                deal=int(row["deal"]),
                config=row["config"],
                solved=bool(row["solved"]),
                timed_out=bool(row["timed_out"]),
                elapsed_ms=float(row["elapsed_ms"]),
                expanded_nodes=int(row["expanded_nodes"]),
                generated_nodes=int(row["generated_nodes"]),
                solution_length=int(row["solution_length"]),
                stop_reason=str(row["stop_reason"]),
            )
        )

    summary_by_cfg = {cfg: _summarize_outcomes(items) for cfg, items in by_cfg.items()}
    delta = _delta_vs_baseline(summary_by_cfg, baseline_config="sort_off_default")

    return {
        "rows": rows,
        "summary": {
            "summary_by_config": summary_by_cfg,
            "delta_vs_sort_off": delta,
        },
        "meta": {
            "deals": deals,
            "trials": trials,
            "timeout_s": timeout_s,
        },
    }


def _benchmark_astar_compaction_toggle(
    deals: list[int],
    trials: int,
    timeout_s: float,
) -> dict[str, Any]:
    configs = [
        ("compaction_on_default", AStarProfile(compact_min_arena_nodes=4096, compact_arena_live_ratio=2)),
        (
            "compaction_off",
            AStarProfile(compact_min_arena_nodes=10**9, compact_arena_live_ratio=10**9),
        ),
    ]

    rows: list[dict[str, Any]] = []
    for trial in range(1, trials + 1):
        for deal in deals:
            for name, profile in configs:
                outcome = _run_solver_single(
                    algorithm="A*",
                    deal=deal,
                    timeout_s=timeout_s,
                    config_name=name,
                    astar_profile=profile,
                )
                rows.append(
                    {
                        "group": "astar_compaction_toggle",
                        "algorithm": "A*",
                        "deal": deal,
                        "trial": trial,
                        "config": name,
                        "elapsed_ms": outcome.elapsed_ms,
                        "expanded_nodes": outcome.expanded_nodes,
                        "generated_nodes": outcome.generated_nodes,
                        "solved": outcome.solved,
                        "timed_out": outcome.timed_out,
                        "solution_length": outcome.solution_length,
                        "stop_reason": outcome.stop_reason,
                    }
                )

    by_cfg: dict[str, list[RunOutcome]] = {name: [] for name, _ in configs}
    for row in rows:
        by_cfg[row["config"]].append(
            RunOutcome(
                algorithm="A*",
                deal=int(row["deal"]),
                config=row["config"],
                solved=bool(row["solved"]),
                timed_out=bool(row["timed_out"]),
                elapsed_ms=float(row["elapsed_ms"]),
                expanded_nodes=int(row["expanded_nodes"]),
                generated_nodes=int(row["generated_nodes"]),
                solution_length=int(row["solution_length"]),
                stop_reason=str(row["stop_reason"]),
            )
        )

    summary_by_cfg = {cfg: _summarize_outcomes(items) for cfg, items in by_cfg.items()}
    delta = _delta_vs_baseline(summary_by_cfg, baseline_config="compaction_on_default")

    return {
        "rows": rows,
        "summary": {
            "summary_by_config": summary_by_cfg,
            "delta_vs_compaction_on": delta,
        },
        "meta": {
            "deals": deals,
            "trials": trials,
            "timeout_s": timeout_s,
        },
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark grouped optimization ablations + Zobrist replacement comparison"
    )
    parser.add_argument("--start-deal", type=int, default=1)
    parser.add_argument("--end-deal", type=int, default=5)
    parser.add_argument("--trials", type=int, default=1)

    parser.add_argument("--group-timeout-s", type=float, default=6.0)
    parser.add_argument("--key-max-expand", type=int, default=20000)
    parser.add_argument(
        "--key-algorithms",
        type=str,
        default="BFS,UCS,A*",
        help="Comma-separated subset of BFS,DFS,UCS,A* for key-mode benchmark",
    )

    parser.add_argument("--output-dir", type=str, default="benchmark_results")
    parser.add_argument(
        "--groups",
        type=str,
        default="state_key_modes,ucs_rule_engine_ablation,ucs_sort_toggle,astar_compaction_toggle",
        help=(
            "Comma-separated subset of: "
            "state_key_modes,ucs_rule_engine_ablation,ucs_sort_toggle,astar_compaction_toggle"
        ),
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.start_deal <= 0 or args.end_deal < args.start_deal:
        raise ValueError("Invalid deal range")
    if args.trials <= 0:
        raise ValueError("--trials must be > 0")
    if args.group_timeout_s <= 0:
        raise ValueError("--group-timeout-s must be > 0")
    if args.key_max_expand <= 0:
        raise ValueError("--key-max-expand must be > 0")

    key_algorithms = [part.strip() for part in args.key_algorithms.split(",") if part.strip()]
    allowed_algorithms = {"BFS", "DFS", "UCS", "A*"}
    unknown = [name for name in key_algorithms if name not in allowed_algorithms]
    if unknown:
        raise ValueError(f"Unknown key algorithms: {unknown}")

    selected_groups = [part.strip() for part in str(args.groups).split(",") if part.strip()]
    allowed_groups = {
        "state_key_modes",
        "ucs_rule_engine_ablation",
        "ucs_sort_toggle",
        "astar_compaction_toggle",
    }
    unknown_groups = [name for name in selected_groups if name not in allowed_groups]
    if unknown_groups:
        raise ValueError(f"Unknown groups: {unknown_groups}")
    if not selected_groups:
        raise ValueError("--groups must contain at least one group")

    deals = list(range(args.start_deal, args.end_deal + 1))

    # Keep benchmark logs quiet and deterministic for fair comparisons.
    os.environ["BFS_RUNTIME_LOG"] = "0"
    os.environ["DFS_RUNTIME_LOG"] = "0"
    os.environ["UCS_RUNTIME_LOG"] = "0"
    os.environ["ASTAR_RUNTIME_LOG"] = "0"

    started = perf_counter()
    groups_payload: dict[str, Any] = {}

    if "state_key_modes" in selected_groups:
        groups_payload["state_key_modes"] = _benchmark_state_key_modes(
            deals=deals,
            trials=int(args.trials),
            timeout_s=float(args.group_timeout_s),
            max_expand=int(args.key_max_expand),
            algorithms=key_algorithms,
        )

    if "ucs_rule_engine_ablation" in selected_groups:
        groups_payload["ucs_rule_engine_ablation"] = _benchmark_ucs_rule_engine_ablation(
            deals=deals,
            trials=int(args.trials),
            timeout_s=float(args.group_timeout_s),
        )

    if "ucs_sort_toggle" in selected_groups:
        groups_payload["ucs_sort_toggle"] = _benchmark_ucs_sort_toggle(
            deals=deals,
            trials=int(args.trials),
            timeout_s=float(args.group_timeout_s),
        )

    if "astar_compaction_toggle" in selected_groups:
        groups_payload["astar_compaction_toggle"] = _benchmark_astar_compaction_toggle(
            deals=deals,
            trials=int(args.trials),
            timeout_s=float(args.group_timeout_s),
        )

    elapsed_sec = perf_counter() - started

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / args.output_dir / f"optimization_groups_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "benchmark": "optimization_groups",
        "run": {
            "start_deal": args.start_deal,
            "end_deal": args.end_deal,
            "trials": args.trials,
            "group_timeout_s": args.group_timeout_s,
            "key_max_expand": args.key_max_expand,
            "key_algorithms": key_algorithms,
            "selected_groups": selected_groups,
            "elapsed_sec_total": elapsed_sec,
        },
        "groups": groups_payload,
        "artifacts": {
            "output_dir": str(out_dir),
        },
    }

    _write_json(out_dir / "report.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
