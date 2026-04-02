"""Logic-faithful benchmark: packed vs unpacked state keys.

This script benchmarks the real solver implementations from backend/solver
instead of re-implementing search loops. It only injects minimal hooks for:
- expansion/time limits
- packed vs unpacked state-key mode switching
- optional tracemalloc peak memory capture
- anti-jitter controls (warmup/order randomization/gc handling)
"""

import argparse
import gc
import os
import random
import statistics
import sys
import tracemalloc
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import backend.solver.astar as astar_module
import backend.solver.bfs as bfs_module
import backend.solver.dfs as dfs_module
import backend.solver.search_utils.ucs_utils as ucs_utils
import backend.solver.ucs as ucs_module
from backend.engine.shuffle import deal_by_game_number
from backend.model.state import State
from backend.solver.astar import AStarAlgorithm
from backend.solver.bfs import BFSAlgorithm
from backend.solver.dfs import DFSAlgorithm
from backend.solver.ucs import UCSAlgorithm
from backend.solver.utils.heuristics import combined_heuristic

PACKED_MODE = "packed"
UNPACKED_MODE = "unpacked"
ALL_MODES = (PACKED_MODE, UNPACKED_MODE)
ALL_ALGOS = ("BFS", "DFS", "UCS", "A*")


class ExpansionLimitReached(RuntimeError):
    """Raised when expansion counter reaches configured limit."""


class TimeoutReached(RuntimeError):
    """Raised when run elapsed time reaches configured timeout."""


@dataclass
class _Counters:
    expanded_nodes: int = 0
    generated_nodes: int = 0
    unique_keys: set | None = None

    def __post_init__(self):
        if self.unique_keys is None:
            self.unique_keys = set()


@dataclass(frozen=True)
class RunResult:
    mode: str
    algorithm: str
    deal: int
    max_expand: int
    expanded_nodes: int
    generated_nodes: int
    elapsed_s: float
    expanded_per_sec: float
    unique_states: int
    stop_reason: str
    peak_bytes: int | None = None


def _build_initial_state(deal_number: int) -> State:
    tableau = deal_by_game_number(deal_number)
    return State.from_lists(
        tableau=tableau,
        freecells=[None] * 4,
        foundations=[[] for _ in range(4)],
    )


def _parse_csv_list(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


def _parse_modes(raw: str) -> list[str]:
    modes = _parse_csv_list(raw)
    if not modes:
        raise ValueError("--modes must contain at least one value")
    unknown = [mode for mode in modes if mode not in ALL_MODES]
    if unknown:
        raise ValueError(f"Unknown mode(s): {unknown}. Allowed: {', '.join(ALL_MODES)}")
    return modes


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


def _mode_order_for_trial(
    modes: list[str],
    trial_index: int,
    rng: random.Random,
    randomize_mode_order: bool,
) -> list[str]:
    ordered = list(modes)
    if randomize_mode_order:
        rng.shuffle(ordered)
        return ordered

    if len(ordered) == 2 and trial_index % 2 == 1:
        ordered.reverse()
    return ordered


def _select_key_func(mode: str) -> Callable[[State], object]:
    if mode == PACKED_MODE:
        return lambda state: state.board_code
    if mode == UNPACKED_MODE:
        return lambda state: (state.tableau, state.freecells, state.foundations)
    raise ValueError(f"Unsupported mode: {mode}")


@contextmanager
def _state_key_mode(mode: str):
    original_utils_state_id = ucs_utils.state_id
    original_ucs_state_id = ucs_module.state_id
    original_astar_state_id = astar_module.state_id
    original_state_hash = State.__hash__

    if mode == PACKED_MODE:
        selected_state_id = lambda state: state.board_code
        selected_hash = lambda state: hash(state.board_code)
    elif mode == UNPACKED_MODE:
        selected_state_id = lambda state: (
            state.tableau,
            state.freecells,
            state.foundations,
        )
        selected_hash = lambda state: hash(
            (state.tableau, state.freecells, state.foundations)
        )
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    ucs_utils.state_id = selected_state_id
    ucs_module.state_id = selected_state_id
    astar_module.state_id = selected_state_id
    State.__hash__ = selected_hash

    try:
        yield
    finally:
        ucs_utils.state_id = original_utils_state_id
        ucs_module.state_id = original_ucs_state_id
        astar_module.state_id = original_astar_state_id
        State.__hash__ = original_state_hash


@contextmanager
def _instrument_get_valid_moves(
    algorithm: str,
    key_of: Callable[[State], object],
    counters: _Counters,
    max_expand: int,
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

        if counters.expanded_nodes >= max_expand:
            raise ExpansionLimitReached()

        counters.expanded_nodes += 1
        counters.unique_keys.add(key_of(state))

        moves = original_get_valid_moves(state, *args, **kwargs)
        counters.generated_nodes += len(moves)
        return moves

    module.get_valid_moves = wrapped_get_valid_moves
    try:
        yield
    finally:
        module.get_valid_moves = original_get_valid_moves


def _run_solver_logic_faithful(
    mode: str,
    algorithm: str,
    deal: int,
    max_expand: int,
    timeout_s: float | None,
    astar_weight: float,
    measure_memory: bool,
    disable_gc_during_measurement: bool,
) -> RunResult:
    key_of = _select_key_func(mode)
    counters = _Counters()
    started_at = perf_counter()
    peak_bytes: int | None = None
    stop_reason = "unknown"

    gc_was_enabled = gc.isenabled()
    if disable_gc_during_measurement and gc_was_enabled:
        gc.disable()

    if measure_memory:
        tracemalloc.start()

    try:
        with _state_key_mode(mode):
            initial_state = _build_initial_state(deal)

            with _instrument_get_valid_moves(
                algorithm=algorithm,
                key_of=key_of,
                counters=counters,
                max_expand=max_expand,
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
                    solver = UCSAlgorithm(initial_state, should_cancel=lambda: False)
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

                stop_reason = (
                    "solution_found" if path is not None else "frontier_exhausted"
                )

    except ExpansionLimitReached:
        stop_reason = "max_expand"
    except TimeoutReached:
        stop_reason = "timeout"
    finally:
        if measure_memory:
            _, peak_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        if disable_gc_during_measurement and gc_was_enabled:
            gc.enable()

    elapsed_s = perf_counter() - started_at
    expanded = counters.expanded_nodes
    return RunResult(
        mode=mode,
        algorithm=algorithm,
        deal=deal,
        max_expand=max_expand,
        expanded_nodes=expanded,
        generated_nodes=counters.generated_nodes,
        elapsed_s=elapsed_s,
        expanded_per_sec=(expanded / elapsed_s) if elapsed_s > 0 else 0.0,
        unique_states=len(counters.unique_keys),
        stop_reason=stop_reason,
        peak_bytes=peak_bytes,
    )


def _print_algorithm_block(
    algorithm: str,
    deal: int,
    max_expand: int,
    trials: int,
    mode_runs: dict[str, list[RunResult]],
) -> None:
    print(f"\n=== {algorithm} Expansion Speed (Solver Logic): Packed vs Unpacked ===")
    print(f"seed={deal} target_expansions={max_expand} trials={trials}")

    packed_runs = mode_runs.get(PACKED_MODE, [])
    unpacked_runs = mode_runs.get(UNPACKED_MODE, [])

    if packed_runs:
        packed_last = packed_runs[-1]
        packed_mean = statistics.mean(run.elapsed_s for run in packed_runs)
        packed_median = statistics.median(run.elapsed_s for run in packed_runs)
        packed_stdev = (
            statistics.stdev(run.elapsed_s for run in packed_runs)
            if len(packed_runs) > 1
            else 0.0
        )
        packed_rate = (max_expand / packed_mean) if packed_mean > 0 else 0.0
        print(f"packed_unique_last_trial={packed_last.unique_states}")
        print(f"packed_mean={packed_mean:.6f}s packed_rate={packed_rate:.2f} nodes/s")
        print(f"packed_median={packed_median:.6f}s packed_stdev={packed_stdev:.6f}s")

    if unpacked_runs:
        unpacked_last = unpacked_runs[-1]
        unpacked_mean = statistics.mean(run.elapsed_s for run in unpacked_runs)
        unpacked_median = statistics.median(run.elapsed_s for run in unpacked_runs)
        unpacked_stdev = (
            statistics.stdev(run.elapsed_s for run in unpacked_runs)
            if len(unpacked_runs) > 1
            else 0.0
        )
        unpacked_rate = (max_expand / unpacked_mean) if unpacked_mean > 0 else 0.0
        print(f"unpacked_unique_last_trial={unpacked_last.unique_states}")
        print(
            f"unpacked_mean={unpacked_mean:.6f}s unpacked_rate={unpacked_rate:.2f} nodes/s"
        )
        print(
            f"unpacked_median={unpacked_median:.6f}s unpacked_stdev={unpacked_stdev:.6f}s"
        )

    if packed_runs and unpacked_runs:
        packed_mean = statistics.mean(run.elapsed_s for run in packed_runs)
        unpacked_mean = statistics.mean(run.elapsed_s for run in unpacked_runs)
        speed_ratio = (unpacked_mean / packed_mean) if packed_mean > 0 else float("inf")
        print(f"packed_over_unpacked_speed={speed_ratio:.3f}x")


def _mean_peak_bytes(runs: list[RunResult]) -> float | None:
    values = [run.peak_bytes for run in runs if run.peak_bytes is not None]
    if not values:
        return None
    return float(statistics.mean(values))


def _mean_bytes_per_unique_state(runs: list[RunResult]) -> float | None:
    values = [
        run.peak_bytes / run.unique_states
        for run in runs
        if run.peak_bytes is not None and run.unique_states > 0
    ]
    if not values:
        return None
    return float(statistics.mean(values))


def _print_memory_block(
    algorithm: str,
    memory_trials: int,
    mode_runs: dict[str, list[RunResult]],
) -> None:
    print(f"\n=== {algorithm} Peak Memory (tracemalloc, Solver Logic) ===")
    print(f"memory_trials={memory_trials}")

    packed_runs = mode_runs.get(PACKED_MODE, [])
    unpacked_runs = mode_runs.get(UNPACKED_MODE, [])

    packed_peak_mean = _mean_peak_bytes(packed_runs)
    unpacked_peak_mean = _mean_peak_bytes(unpacked_runs)

    if packed_peak_mean is not None:
        print(f"packed_peak_mean={packed_peak_mean / (1024 * 1024):.3f} MB")

    if unpacked_peak_mean is not None:
        print(f"unpacked_peak_mean={unpacked_peak_mean / (1024 * 1024):.3f} MB")

    if (
        packed_peak_mean is not None
        and unpacked_peak_mean is not None
        and packed_peak_mean > 0
    ):
        print(
            f"unpacked_over_packed_memory={unpacked_peak_mean / packed_peak_mean:.3f}x"
        )

    packed_bytes_per_unique = _mean_bytes_per_unique_state(packed_runs)
    unpacked_bytes_per_unique = _mean_bytes_per_unique_state(unpacked_runs)

    if packed_bytes_per_unique is not None:
        print(f"packed_bytes_per_unique_state={packed_bytes_per_unique:.1f}")
    if unpacked_bytes_per_unique is not None:
        print(f"unpacked_bytes_per_unique_state={unpacked_bytes_per_unique:.1f}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Logic-faithful benchmark for packed vs unpacked keys"
    )
    parser.add_argument(
        "--deal", type=int, default=1, help="Single deal number to benchmark"
    )
    parser.add_argument(
        "--modes",
        type=str,
        default="packed,unpacked",
        help="Comma-separated list: packed,unpacked",
    )
    parser.add_argument(
        "--algorithms",
        type=str,
        default="BFS,DFS,UCS,A*",
        help="Comma-separated list from BFS,DFS,UCS,A*",
    )
    parser.add_argument(
        "--max-expand",
        type=int,
        default=100000,
        help="Maximum expansions per run",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=None,
        help="Optional timeout per run in seconds",
    )
    parser.add_argument(
        "--astar-weight",
        type=float,
        default=5.0,
        help="A* heuristic weight",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=5,
        help="Measured trials per mode/algorithm",
    )
    parser.add_argument(
        "--memory-trials",
        type=int,
        default=3,
        help="Memory trials per mode/algorithm",
    )
    parser.add_argument(
        "--warmup-trials",
        type=int,
        default=1,
        help="Warmup trials before measured runs",
    )
    parser.add_argument(
        "--randomize-mode-order",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Shuffle mode order per trial to reduce ordering bias",
    )
    parser.add_argument(
        "--order-seed",
        type=int,
        default=1403,
        help="Seed for mode-order randomization",
    )
    parser.add_argument(
        "--gc-between-runs",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run gc.collect() before each trial",
    )
    parser.add_argument(
        "--disable-gc-during-measurement",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Disable Python GC while a timed run is executing",
    )
    args = parser.parse_args()

    if args.max_expand <= 0:
        raise ValueError("--max-expand must be > 0")
    if args.timeout_s is not None and args.timeout_s <= 0:
        raise ValueError("--timeout-s must be > 0 when provided")
    if args.astar_weight <= 0:
        raise ValueError("--astar-weight must be > 0")
    if args.trials <= 0:
        raise ValueError("--trials must be > 0")
    if args.memory_trials < 0:
        raise ValueError("--memory-trials must be >= 0")
    if args.warmup_trials < 0:
        raise ValueError("--warmup-trials must be >= 0")

    modes = _parse_modes(args.modes)
    algorithms = _parse_algorithms(args.algorithms)

    # Disable verbose runtime logs inside solver classes during benchmark.
    os.environ["UCS_RUNTIME_LOG"] = "0"
    os.environ["ASTAR_RUNTIME_LOG"] = "0"

    print("Benchmark stabilization config")
    print("- logic_source=backend/solver (faithful)")
    print(f"- warmup_trials={args.warmup_trials}")
    print(f"- randomize_mode_order={args.randomize_mode_order}")
    print(f"- order_seed={args.order_seed}")
    print(f"- gc_between_runs={args.gc_between_runs}")
    print(f"- disable_gc_during_measurement={args.disable_gc_during_measurement}")

    for algorithm in algorithms:
        algorithm_seed = args.order_seed + sum(ord(ch) for ch in algorithm)
        speed_rng = random.Random(algorithm_seed)
        memory_rng = random.Random(algorithm_seed + 100_003)

        for warmup_idx in range(args.warmup_trials):
            for mode in _mode_order_for_trial(
                modes, warmup_idx, speed_rng, args.randomize_mode_order
            ):
                if args.gc_between_runs:
                    gc.collect()
                _run_solver_logic_faithful(
                    mode=mode,
                    algorithm=algorithm,
                    deal=args.deal,
                    max_expand=args.max_expand,
                    timeout_s=args.timeout_s,
                    astar_weight=args.astar_weight,
                    measure_memory=False,
                    disable_gc_during_measurement=args.disable_gc_during_measurement,
                )

        mode_runs: dict[str, list[RunResult]] = {mode: [] for mode in modes}
        for trial_idx in range(args.trials):
            for mode in _mode_order_for_trial(
                modes, trial_idx, speed_rng, args.randomize_mode_order
            ):
                if args.gc_between_runs:
                    gc.collect()
                run = _run_solver_logic_faithful(
                    mode=mode,
                    algorithm=algorithm,
                    deal=args.deal,
                    max_expand=args.max_expand,
                    timeout_s=args.timeout_s,
                    astar_weight=args.astar_weight,
                    measure_memory=False,
                    disable_gc_during_measurement=args.disable_gc_during_measurement,
                )
                mode_runs[mode].append(run)

        _print_algorithm_block(
            algorithm=algorithm,
            deal=args.deal,
            max_expand=args.max_expand,
            trials=args.trials,
            mode_runs=mode_runs,
        )

        if args.memory_trials > 0:
            memory_runs: dict[str, list[RunResult]] = {mode: [] for mode in modes}
            for trial_idx in range(args.memory_trials):
                for mode in _mode_order_for_trial(
                    modes, trial_idx, memory_rng, args.randomize_mode_order
                ):
                    if args.gc_between_runs:
                        gc.collect()
                    run = _run_solver_logic_faithful(
                        mode=mode,
                        algorithm=algorithm,
                        deal=args.deal,
                        max_expand=args.max_expand,
                        timeout_s=args.timeout_s,
                        astar_weight=args.astar_weight,
                        measure_memory=True,
                        disable_gc_during_measurement=args.disable_gc_during_measurement,
                    )
                    memory_runs[mode].append(run)

            _print_memory_block(
                algorithm=algorithm,
                memory_trials=args.memory_trials,
                mode_runs=memory_runs,
            )

    if args.timeout_s is not None:
        print(
            f"\nNote: Runs were limited to a maximum of {args.timeout_s:.3f} seconds each."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
