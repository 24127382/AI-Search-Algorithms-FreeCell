"""Uniform Cost Search solver."""

from heapq import heappop, heappush
from time import perf_counter
from typing import Optional

from backend.engine.engine import apply_move_with_forced, get_valid_moves
from backend.experiments.solver_stats import SolverStats
from backend.solver.search_utils.search_profile import UCSProfile
from backend.solver.search_utils.ucs_utils import (
    encode_edge_moves,
    finalize_ucs_outcome,
    reconstruct_interned_path,
    ucs_move_cost,
)
from backend.solver.utils.utility import state_id, structural_priority_bias


class UCSAlgorithm:
    """Uniform-Cost Search with exact single-mode execution.

    Attributes:
        game_state: Initial search state.
        last_run_stats: Statistics from last completed run.
    """

    def __init__(
        self, game_state, should_cancel=None, profile: Optional[UCSProfile] = None
    ):
        """Initialize UCS with a fixed start state.

        Args:
            game_state: Initial search state.
            should_cancel: Optional callable returning True when search should stop.
        """
        self.game_state = game_state
        self.should_cancel = should_cancel or (lambda: False)
        self.profile = profile or UCSProfile.from_env()
        self.last_run_stats = None

    def search(self):
        """Run UCS and return an optimal path if one exists.

        Returns:
            list | None: Solution path, or `None` when no solution was found.
        """
        started_at = perf_counter()
        counter = 0
        start_state = self.game_state
        start_state_id = state_id(start_state)

        frontier = []
        heappush(
            frontier,
            (0, structural_priority_bias(start_state), counter, start_state_id),
        )

        stats = SolverStats.ucs_defaults()

        best_cost = {start_state_id: 0}
        best_node_index = {start_state_id: 0}
        parent_index_arena = [-1]
        edge_move_ids_arena = [()]

        move_pool = []
        move_index_by_signature = {}

        state_cache = {start_state_id: start_state}

        while frontier:
            if self.should_cancel():
                stats["stop_reason"] = "cancelled"
                stats["solution_length"] = 0
                self.last_run_stats = finalize_ucs_outcome(
                    stats,
                    started_at,
                    solution_found=False,
                    move_pool_size=len(move_pool),
                    frontier_size=len(frontier),
                    visited_size=len(best_cost),
                    runtime_log_enabled=self.profile.runtime_log_enabled,
                )
                return None

            if len(frontier) > stats["peak_frontier_size"]:
                stats["peak_frontier_size"] = len(frontier)
            if len(best_cost) > stats["peak_visited_size"]:
                stats["peak_visited_size"] = len(best_cost)
            if len(state_cache) > stats["peak_state_cache_size"]:
                stats["peak_state_cache_size"] = len(state_cache)

            cost, _, _, current_state_id = heappop(frontier)
            best_known_cost = best_cost.get(current_state_id)
            if best_known_cost is None or cost != best_known_cost:
                stats["stale_heap_pops"] += 1
                continue

            current_node_index = best_node_index.get(current_state_id)
            if current_node_index is None:
                stats["stale_heap_pops"] += 1
                continue

            current_state = state_cache.pop(current_state_id, None)
            if current_state is None:
                stats["stale_heap_pops"] += 1
                continue

            stats["expanded_nodes"] += 1

            if current_state.is_goal:
                path = reconstruct_interned_path(
                    current_node_index,
                    parent_index_arena,
                    edge_move_ids_arena,
                    move_pool,
                )
                stats["move_pool_size"] = len(move_pool)
                stats["stop_reason"] = "solved"
                stats["solution_cost"] = cost
                stats["solution_length"] = len(path)
                stats["final_frontier_size"] = len(frontier)
                stats["final_visited_size"] = len(best_cost)
                self.last_run_stats = SolverStats.finalize_ucs(
                    stats, started_at, solution_found=True
                )
                if self.profile.runtime_log_enabled:
                    print(SolverStats.format_ucs(self.last_run_stats))
                return path

            incoming_edge_move_ids = edge_move_ids_arena[current_node_index]
            last_move = (
                move_pool[incoming_edge_move_ids[-1]]
                if incoming_edge_move_ids
                else None
            )
            candidate_moves = get_valid_moves(
                current_state,
                last_move=last_move,
                prune_canonical_redundant=True,
            )

            for move in candidate_moves:
                if self.should_cancel():
                    stats["stop_reason"] = "cancelled"
                    stats["solution_length"] = 0
                    self.last_run_stats = finalize_ucs_outcome(
                        stats,
                        started_at,
                        solution_found=False,
                        move_pool_size=len(move_pool),
                        frontier_size=len(frontier),
                        visited_size=len(best_cost),
                        runtime_log_enabled=self.profile.runtime_log_enabled,
                    )
                    return None

                next_state, forced_moves = apply_move_with_forced(current_state, move)
                edge_cost = ucs_move_cost(
                    move, prev_state=current_state, next_state=next_state
                )
                if forced_moves:
                    edge_cost += sum(
                        ucs_move_cost(applied_move) for applied_move in forced_moves
                    )

                edge_moves = (move, *forced_moves)
                next_state_id = state_id(next_state)
                new_cost = cost + edge_cost
                stats["generated_nodes"] += 1

                old_cost = best_cost.get(next_state_id)
                if old_cost is not None and new_cost >= old_cost:
                    stats["dominance_pruned"] += 1
                    continue

                edge_move_ids = encode_edge_moves(
                    edge_moves, move_index_by_signature, move_pool
                )
                node_index = len(parent_index_arena)
                best_cost[next_state_id] = new_cost
                best_node_index[next_state_id] = node_index
                parent_index_arena.append(current_node_index)
                edge_move_ids_arena.append(edge_move_ids)
                state_cache[next_state_id] = next_state
                counter += 1
                heappush(
                    frontier,
                    (
                        new_cost,
                        structural_priority_bias(next_state),
                        counter,
                        next_state_id,
                    ),
                )

        stats["stop_reason"] = "exhausted"
        stats["solution_length"] = 0
        self.last_run_stats = finalize_ucs_outcome(
            stats,
            started_at,
            solution_found=False,
            move_pool_size=len(move_pool),
            frontier_size=len(frontier),
            visited_size=len(best_cost),
            runtime_log_enabled=self.profile.runtime_log_enabled,
        )
        return None
