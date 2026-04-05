"""Microbenchmarks for model/state and rule primitives.

This benchmark intentionally avoids running full solver loops.
It focuses on low-level throughput and memory-per-state signals.
"""

from __future__ import annotations

import argparse
import gc
import json
import statistics
import tracemalloc
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

from source.application.engine.engine import get_valid_moves
from source.application.services.game_service import GameService
from source.domain.model.card import Card, VALID_RANK, VALID_SUITS
from source.domain.model.state import State
from source.domain.rule import rules as rules_module
from source.domain.rule.rules import (
    can_move_to_tableau,
    get_max_sequence_length,
    get_max_sequence_to_empty_tableau,
    get_movable_sequences,
)


@dataclass(frozen=True)
class TransitionPayload:
    prev_state: State
    tableau: tuple[tuple[Card, ...], ...]
    freecells: tuple[Card | None, ...]
    foundations: tuple[tuple[Card, ...], ...]
    touched_tableau_indices: tuple[int, ...]


def _safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.fmean(values))


def _build_states(start_deal: int, end_deal: int) -> list[State]:
    states: list[State] = []
    for deal in range(start_deal, end_deal + 1):
        _, state = GameService.build_initial_state(deal)
        states.append(state)
    return states


def _apply_move_structures(
    state: State,
    move,
) -> tuple[
    tuple[tuple[Card, ...], ...],
    tuple[Card | None, ...],
    tuple[tuple[Card, ...], ...],
    tuple[int, ...],
]:
    tableau = list(state.tableau)
    freecells = list(state.freecells)
    foundations = list(state.foundations)

    from_type, from_idx = move.from_pos
    to_type, to_idx = move.to_pos

    touched: list[int] = []
    moving_cards = move.sequence if move.sequence else (move.card,)

    if from_type == "tableau":
        source_col = tableau[from_idx]
        move_len = len(moving_cards)
        moving_cards = source_col[-move_len:]
        tableau[from_idx] = source_col[:-move_len]
        touched.append(from_idx)
    elif from_type == "freecell":
        freecells[from_idx] = None

    if to_type == "tableau":
        dest_col = tableau[to_idx]
        tableau[to_idx] = dest_col + tuple(moving_cards)
        touched.append(to_idx)
    elif to_type == "freecell":
        freecells[to_idx] = moving_cards[0]
    elif to_type == "foundation":
        dest_stack = foundations[to_idx]
        foundations[to_idx] = dest_stack + (moving_cards[0],)

    return (
        tuple(tableau),
        tuple(freecells),
        tuple(foundations),
        tuple(dict.fromkeys(touched)),
    )


def _build_transition_payloads(states: list[State]) -> list[TransitionPayload]:
    payloads: list[TransitionPayload] = []
    for state in states:
        moves = get_valid_moves(
            state,
            prune_safe=False,
            last_move=None,
            prune_canonical_redundant=True,
            sort_moves=True,
        )
        if not moves:
            continue
        move = moves[0]
        tableau, freecells, foundations, touched = _apply_move_structures(state, move)
        payloads.append(
            TransitionPayload(
                prev_state=state,
                tableau=tableau,
                freecells=freecells,
                foundations=foundations,
                touched_tableau_indices=touched,
            )
        )
    return payloads


def _measure_peak_allocation(work) -> tuple[int, int]:
    gc.collect()
    tracemalloc.start()
    start_current, _ = tracemalloc.get_traced_memory()
    op_count = int(work())
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return max(0, peak - start_current), op_count


def _run_model_benchmarks(
    states: list[State],
    transition_payloads: list[TransitionPayload],
    loops: int,
) -> dict[str, Any]:
    raw_state_structs = [
        (state.tableau, state.freecells, state.foundations) for state in states
    ]

    def create_from_lists_work() -> int:
        created = 0
        for _ in range(loops):
            for tableau, freecells, foundations in raw_state_structs:
                State.from_lists(tableau, freecells, foundations)
                created += 1
        return created

    t0 = perf_counter()
    from_lists_ops = create_from_lists_work()
    from_lists_elapsed = perf_counter() - t0

    from_lists_peak_bytes, from_lists_mem_ops = _measure_peak_allocation(
        create_from_lists_work
    )

    def incremental_transition_work() -> int:
        built = 0
        for _ in range(loops):
            for payload in transition_payloads:
                State.from_transition(
                    prev_state=payload.prev_state,
                    tableau=payload.tableau,
                    freecells=payload.freecells,
                    foundations=payload.foundations,
                    touched_tableau_indices=payload.touched_tableau_indices,
                )
                built += 1
        return built

    t1 = perf_counter()
    transition_ops = incremental_transition_work()
    transition_elapsed = perf_counter() - t1

    transition_peak_bytes, transition_mem_ops = _measure_peak_allocation(
        incremental_transition_work
    )

    def rebuild_transition_work() -> int:
        built = 0
        for _ in range(loops):
            for payload in transition_payloads:
                State.from_lists(payload.tableau, payload.freecells, payload.foundations)
                built += 1
        return built

    t2 = perf_counter()
    rebuild_ops = rebuild_transition_work()
    rebuild_elapsed = perf_counter() - t2

    rebuild_peak_bytes, rebuild_mem_ops = _measure_peak_allocation(
        rebuild_transition_work
    )

    incremental_vs_rebuild = None
    if transition_elapsed > 0 and rebuild_elapsed > 0:
        incremental_vs_rebuild = rebuild_elapsed / transition_elapsed

    return {
        "state_create_from_lists": {
            "ops": from_lists_ops,
            "elapsed_s": from_lists_elapsed,
            "throughput_ops_per_sec": (
                from_lists_ops / from_lists_elapsed if from_lists_elapsed > 0 else None
            ),
            "peak_alloc_bytes": from_lists_peak_bytes,
            "bytes_per_state": (
                from_lists_peak_bytes / from_lists_mem_ops
                if from_lists_mem_ops > 0
                else None
            ),
        },
        "state_transition_incremental": {
            "ops": transition_ops,
            "elapsed_s": transition_elapsed,
            "throughput_ops_per_sec": (
                transition_ops / transition_elapsed if transition_elapsed > 0 else None
            ),
            "peak_alloc_bytes": transition_peak_bytes,
            "bytes_per_state": (
                transition_peak_bytes / transition_mem_ops
                if transition_mem_ops > 0
                else None
            ),
        },
        "state_transition_full_rebuild": {
            "ops": rebuild_ops,
            "elapsed_s": rebuild_elapsed,
            "throughput_ops_per_sec": (
                rebuild_ops / rebuild_elapsed if rebuild_elapsed > 0 else None
            ),
            "peak_alloc_bytes": rebuild_peak_bytes,
            "bytes_per_state": (
                rebuild_peak_bytes / rebuild_mem_ops
                if rebuild_mem_ops > 0
                else None
            ),
        },
        "highlights": {
            "incremental_vs_full_rebuild_speed_x": incremental_vs_rebuild,
            "incremental_vs_full_rebuild_memory_ratio": (
                (transition_peak_bytes / rebuild_peak_bytes)
                if rebuild_peak_bytes > 0
                else None
            ),
        },
    }


def _naive_can_move_to_tableau(card: Card, tableau_col: tuple[Card, ...]) -> bool:
    if not tableau_col:
        return True
    top_card = tableau_col[-1]
    return (card.rank_val == top_card.rank_val - 1) and (card.color != top_card.color)


def _run_rule_benchmarks(states: list[State], loops: int) -> dict[str, Any]:
    deck = [Card(suit, rank) for suit in VALID_SUITS for rank in VALID_RANK]
    pairs = [(moving, top) for moving in deck for top in deck]

    t0 = perf_counter()
    fast_true_count = 0
    for _ in range(loops):
        for moving, top in pairs:
            if can_move_to_tableau(moving, (top,)):
                fast_true_count += 1
    fast_elapsed = perf_counter() - t0

    t1 = perf_counter()
    naive_true_count = 0
    for _ in range(loops):
        for moving, top in pairs:
            if _naive_can_move_to_tableau(moving, (top,)):
                naive_true_count += 1
    naive_elapsed = perf_counter() - t1

    columns = [col for state in states for col in state.tableau if col]
    if not columns:
        columns = [tuple()]

    rules_module._get_movable_sequences_cached.cache_clear()
    t2 = perf_counter()
    warm_seq_sizes: list[int] = []
    for _ in range(loops):
        for column in columns:
            warm_seq_sizes.append(len(get_movable_sequences(column)))
    warm_elapsed = perf_counter() - t2

    t3 = perf_counter()
    cold_seq_sizes: list[int] = []
    for _ in range(loops):
        rules_module._get_movable_sequences_cached.cache_clear()
        for column in columns:
            cold_seq_sizes.append(len(get_movable_sequences(column)))
    cold_elapsed = perf_counter() - t3

    t4 = perf_counter()
    seq_limits: list[int] = []
    for _ in range(loops):
        for state in states:
            seq_limits.append(get_max_sequence_length(state))
            seq_limits.append(get_max_sequence_to_empty_tableau(state))
    limit_elapsed = perf_counter() - t4

    pair_ops = loops * len(pairs)
    column_ops = loops * len(columns)
    limit_ops = loops * len(states) * 2

    return {
        "tableau_pair_lookup": {
            "ops": pair_ops,
            "lookup_elapsed_s": fast_elapsed,
            "lookup_ops_per_sec": pair_ops / fast_elapsed if fast_elapsed > 0 else None,
            "naive_elapsed_s": naive_elapsed,
            "naive_ops_per_sec": pair_ops / naive_elapsed if naive_elapsed > 0 else None,
            "lookup_vs_naive_speed_x": (
                naive_elapsed / fast_elapsed
                if fast_elapsed > 0 and naive_elapsed > 0
                else None
            ),
            "lookup_true_count": fast_true_count,
            "naive_true_count": naive_true_count,
        },
        "movable_sequences_cache": {
            "ops": column_ops,
            "warm_elapsed_s": warm_elapsed,
            "warm_ops_per_sec": column_ops / warm_elapsed if warm_elapsed > 0 else None,
            "cold_elapsed_s": cold_elapsed,
            "cold_ops_per_sec": column_ops / cold_elapsed if cold_elapsed > 0 else None,
            "warm_vs_cold_speed_x": (
                cold_elapsed / warm_elapsed
                if warm_elapsed > 0 and cold_elapsed > 0
                else None
            ),
            "mean_sequences_warm": _safe_mean([float(v) for v in warm_seq_sizes]),
            "mean_sequences_cold": _safe_mean([float(v) for v in cold_seq_sizes]),
        },
        "supermove_limit_tables": {
            "ops": limit_ops,
            "elapsed_s": limit_elapsed,
            "ops_per_sec": limit_ops / limit_elapsed if limit_elapsed > 0 else None,
            "mean_limit_value": _safe_mean([float(v) for v in seq_limits]),
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run microbenchmarks for model/state and rule primitives"
    )
    parser.add_argument("--start-deal", type=int, default=1)
    parser.add_argument("--end-deal", type=int, default=30)
    parser.add_argument("--state-loops", type=int, default=500)
    parser.add_argument("--rule-loops", type=int, default=800)
    parser.add_argument("--output-dir", type=str, default="benchmark_results")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.start_deal <= 0 or args.end_deal < args.start_deal:
        raise ValueError("Invalid deal range")
    if args.state_loops <= 0 or args.rule_loops <= 0:
        raise ValueError("Loop counts must be > 0")

    states = _build_states(args.start_deal, args.end_deal)
    transition_payloads = _build_transition_payloads(states)

    started = perf_counter()
    model_results = _run_model_benchmarks(
        states=states,
        transition_payloads=transition_payloads,
        loops=args.state_loops,
    )
    rule_results = _run_rule_benchmarks(states=states, loops=args.rule_loops)
    elapsed_total = perf_counter() - started

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / args.output_dir / f"model_rule_micro_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "benchmark": "model_rule_micro",
        "run": {
            "start_deal": args.start_deal,
            "end_deal": args.end_deal,
            "state_loops": args.state_loops,
            "rule_loops": args.rule_loops,
            "state_count": len(states),
            "transition_sample_count": len(transition_payloads),
            "elapsed_total_s": elapsed_total,
        },
        "results": {
            "model": model_results,
            "rule": rule_results,
        },
        "artifacts": {
            "output_dir": str(out_dir),
        },
    }

    _write_json(out_dir / "report.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
