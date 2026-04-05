"""Ablation benchmark for engine/UCS feature toggles.

This benchmark isolates feature flags that can be toggled safely:
- prune_safe
- immediate-undo pruning
- move ordering
- dominance pruning
- move interning

Runs UCS only with timeout and max-expanded-node limits.
"""

from __future__ import annotations

import argparse
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

# Import engine first to avoid known service/solver circular import during bootstrap.
import source.application.engine.engine as engine_module  # noqa: F401
import source.domain.solver.ucs as ucs_module
from source.application.services.game_service import GameService
from source.domain.solver.search_utils.search_profile import UCSProfile
from source.domain.solver.ucs import UCSAlgorithm


@dataclass(frozen=True)
class FeatureConfig:
    name: str
    prune_safe_moves: bool
    prune_immediate_undo: bool
    sort_candidate_moves: bool
    dominance_pruning_enabled: bool
    move_interning_enabled: bool


def _safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _make_profile(base: UCSProfile, cfg: FeatureConfig) -> UCSProfile:
    payload = base.to_dict()
    payload.update(
        {
            "prune_safe_moves": cfg.prune_safe_moves,
            "prune_immediate_undo": cfg.prune_immediate_undo,
            "sort_candidate_moves": cfg.sort_candidate_moves,
            "dominance_pruning_enabled": cfg.dominance_pruning_enabled,
            "move_interning_enabled": cfg.move_interning_enabled,
            "prune_canonical_redundant": True,
            "runtime_log_enabled": False,
        }
    )
    return UCSProfile.from_dict(payload)


@contextmanager
def _cap_ucs_expansions(max_expanded_nodes: int, counter_ref: dict[str, int], cancel_ref: dict[str, bool]):
    original_get_valid_moves = ucs_module.get_valid_moves

    def wrapped_get_valid_moves(*args, **kwargs):
        if counter_ref["expanded"] >= max_expanded_nodes:
            cancel_ref["max_expand_hit"] = True
            return []
        counter_ref["expanded"] += 1
        return original_get_valid_moves(*args, **kwargs)

    ucs_module.get_valid_moves = wrapped_get_valid_moves
    try:
        yield
    finally:
        ucs_module.get_valid_moves = original_get_valid_moves


def _run_single(
    deal: int,
    timeout_s: float,
    max_expanded_nodes: int,
    cfg: FeatureConfig,
    base_profile: UCSProfile,
) -> dict[str, Any]:
    _, state = GameService.build_initial_state(deal)
    started = perf_counter()

    counters = {"expanded": 0}
    cancel_state = {"max_expand_hit": False}

    def should_cancel() -> bool:
        if cancel_state["max_expand_hit"]:
            return True
        return (perf_counter() - started) >= timeout_s

    profile = _make_profile(base_profile, cfg)

    with _cap_ucs_expansions(max_expanded_nodes, counters, cancel_state):
        solver = UCSAlgorithm(state, should_cancel=should_cancel, profile=profile)
        path = solver.search()

    stats = solver.last_run_stats or {}
    elapsed_ms = float(stats.get("elapsed_ms", (perf_counter() - started) * 1000.0))
    timed_out = (
        bool(path is None)
        and not cancel_state["max_expand_hit"]
        and elapsed_ms >= timeout_s * 1000.0 * 0.98
    )

    stop_reason = str(stats.get("stop_reason", "unknown"))
    if cancel_state["max_expand_hit"]:
        stop_reason = "max_expand"

    return {
        "config": cfg.name,
        "deal": deal,
        "elapsed_ms": elapsed_ms,
        "solved": bool(path is not None),
        "timed_out": timed_out,
        "max_expand_hit": bool(cancel_state["max_expand_hit"]),
        "stop_reason": stop_reason,
        "solution_length": int(stats.get("solution_length", 0)),
        "expanded_nodes": int(stats.get("expanded_nodes", counters["expanded"])),
        "generated_nodes": int(stats.get("generated_nodes", 0)),
        "dominance_pruned": int(stats.get("dominance_pruned", 0)),
        "stale_heap_pops": int(stats.get("stale_heap_pops", 0)),
        "move_pool_size": int(stats.get("move_pool_size", 0)),
        "peak_state_cache_size": int(stats.get("peak_state_cache_size", 0)),
        "final_visited_size": int(stats.get("final_visited_size", 0)),
    }


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_config: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_config.setdefault(row["config"], []).append(row)

    summary: dict[str, Any] = {}
    for cfg, cfg_rows in by_config.items():
        solved_rows = [row for row in cfg_rows if row["solved"]]
        elapsed_all = [float(row["elapsed_ms"]) for row in cfg_rows]
        elapsed_solved = [float(row["elapsed_ms"]) for row in solved_rows]
        expanded_all = [float(row["expanded_nodes"]) for row in cfg_rows]
        generated_all = [float(row["generated_nodes"]) for row in cfg_rows]
        dominance_all = [float(row["dominance_pruned"]) for row in cfg_rows]
        move_pool_all = [float(row["move_pool_size"]) for row in cfg_rows]

        nodes_per_sec = []
        for row in cfg_rows:
            elapsed_s = float(row["elapsed_ms"]) / 1000.0
            if elapsed_s > 0:
                nodes_per_sec.append(float(row["expanded_nodes"]) / elapsed_s)

        summary[cfg] = {
            "cases": len(cfg_rows),
            "solved": sum(1 for row in cfg_rows if row["solved"]),
            "timed_out": sum(1 for row in cfg_rows if row["timed_out"]),
            "max_expand_hits": sum(1 for row in cfg_rows if row["max_expand_hit"]),
            "mean_elapsed_ms_all": _safe_mean(elapsed_all),
            "mean_elapsed_ms_solved": _safe_mean(elapsed_solved),
            "mean_expanded_nodes_all": _safe_mean(expanded_all),
            "mean_generated_nodes_all": _safe_mean(generated_all),
            "mean_dominance_pruned": _safe_mean(dominance_all),
            "mean_move_pool_size": _safe_mean(move_pool_all),
            "mean_expanded_nodes_per_sec": _safe_mean(nodes_per_sec),
        }
    return summary


def _delta_vs_baseline(summary_by_config: dict[str, dict[str, Any]], baseline: str) -> dict[str, Any]:
    base = summary_by_config[baseline]
    base_elapsed = base.get("mean_elapsed_ms_all")
    base_generated = base.get("mean_generated_nodes_all")
    base_expanded = base.get("mean_expanded_nodes_all")

    delta: dict[str, Any] = {}
    for cfg, item in summary_by_config.items():
        elapsed = item.get("mean_elapsed_ms_all")
        generated = item.get("mean_generated_nodes_all")
        expanded = item.get("mean_expanded_nodes_all")

        elapsed_improve = None
        if base_elapsed and elapsed:
            elapsed_improve = ((base_elapsed - elapsed) / base_elapsed) * 100.0

        generated_reduction = None
        if base_generated and generated:
            generated_reduction = ((base_generated - generated) / base_generated) * 100.0

        expanded_reduction = None
        if base_expanded and expanded:
            expanded_reduction = ((base_expanded - expanded) / base_expanded) * 100.0

        delta[cfg] = {
            "elapsed_improve_pct_vs_baseline": elapsed_improve,
            "generated_reduction_pct_vs_baseline": generated_reduction,
            "expanded_reduction_pct_vs_baseline": expanded_reduction,
        }

    return delta


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ablation benchmark for engine/UCS features")
    parser.add_argument("--start-deal", type=int, default=1)
    parser.add_argument("--end-deal", type=int, default=10)
    parser.add_argument("--trials", type=int, default=2)
    parser.add_argument("--timeout-s", type=float, default=60.0)
    parser.add_argument("--max-expanded-nodes", type=int, default=500000)
    parser.add_argument("--output-dir", type=str, default="benchmark_results")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.start_deal <= 0 or args.end_deal < args.start_deal:
        raise ValueError("Invalid deal range")
    if args.trials <= 0:
        raise ValueError("--trials must be > 0")
    if args.timeout_s <= 0:
        raise ValueError("--timeout-s must be > 0")
    if args.max_expanded_nodes <= 0:
        raise ValueError("--max-expanded-nodes must be > 0")

    os.environ["UCS_RUNTIME_LOG"] = "0"

    configs = [
        FeatureConfig(
            name="baseline_full_on",
            prune_safe_moves=True,
            prune_immediate_undo=True,
            sort_candidate_moves=False,
            dominance_pruning_enabled=True,
            move_interning_enabled=True,
        ),
        FeatureConfig(
            name="prune_safe_off",
            prune_safe_moves=False,
            prune_immediate_undo=True,
            sort_candidate_moves=False,
            dominance_pruning_enabled=True,
            move_interning_enabled=True,
        ),
        FeatureConfig(
            name="immediate_undo_off",
            prune_safe_moves=True,
            prune_immediate_undo=False,
            sort_candidate_moves=False,
            dominance_pruning_enabled=True,
            move_interning_enabled=True,
        ),
        FeatureConfig(
            name="move_ordering_on",
            prune_safe_moves=True,
            prune_immediate_undo=True,
            sort_candidate_moves=True,
            dominance_pruning_enabled=True,
            move_interning_enabled=True,
        ),
        FeatureConfig(
            name="dominance_off",
            prune_safe_moves=True,
            prune_immediate_undo=True,
            sort_candidate_moves=False,
            dominance_pruning_enabled=False,
            move_interning_enabled=True,
        ),
        FeatureConfig(
            name="move_interning_off",
            prune_safe_moves=True,
            prune_immediate_undo=True,
            sort_candidate_moves=False,
            dominance_pruning_enabled=True,
            move_interning_enabled=False,
        ),
    ]

    base_profile = UCSProfile.from_env()
    deals = list(range(args.start_deal, args.end_deal + 1))

    rows: list[dict[str, Any]] = []
    started = perf_counter()

    for trial in range(1, args.trials + 1):
        for deal in deals:
            for cfg in configs:
                row = _run_single(
                    deal=deal,
                    timeout_s=float(args.timeout_s),
                    max_expanded_nodes=int(args.max_expanded_nodes),
                    cfg=cfg,
                    base_profile=base_profile,
                )
                row["trial"] = trial
                rows.append(row)

    summary_by_config = _summarize_rows(rows)
    delta = _delta_vs_baseline(summary_by_config, baseline="baseline_full_on")

    elapsed_total = perf_counter() - started
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / args.output_dir / f"engine_ucs_feature_ablation_{timestamp}"

    report = {
        "benchmark": "engine_ucs_feature_ablation",
        "run": {
            "start_deal": args.start_deal,
            "end_deal": args.end_deal,
            "trials": args.trials,
            "timeout_s": args.timeout_s,
            "max_expanded_nodes": args.max_expanded_nodes,
            "elapsed_total_s": elapsed_total,
        },
        "configs": [cfg.__dict__ for cfg in configs],
        "rows": rows,
        "summary": {
            "summary_by_config": summary_by_config,
            "delta_vs_baseline_full_on": delta,
        },
        "artifacts": {
            "output_dir": str(out_dir),
        },
    }

    _write_json(out_dir / "report.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
