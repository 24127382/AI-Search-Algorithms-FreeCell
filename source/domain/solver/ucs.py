"""Uniform Cost Search solver."""

from heapq import heappop, heappush
from time import perf_counter
from typing import Optional

from source.application.engine.engine import apply_move_with_forced, get_valid_moves
from source.application.experiments.solver_stats import SolverStats
from source.domain.solver.search_utils.search_profile import UCSProfile
from source.domain.solver.search_utils.ucs_utils import (
    encode_edge_moves,
    finalize_ucs_outcome,
    reconstruct_interned_path,
    ucs_forced_foundation_chain_cost,
    ucs_move_cost,
)
from source.domain.solver.utils.utility import state_id, structural_priority_bias


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
        should_cancel = self.should_cancel
        profile = self.profile
        inner_cancel_check_interval = profile.inner_cancel_check_interval
        stats_update_interval = profile.stats_update_interval
        sort_candidate_moves = profile.sort_candidate_moves
        prune_safe_moves = profile.prune_safe_moves
        prune_immediate_undo = profile.prune_immediate_undo
        prune_canonical_redundant = profile.prune_canonical_redundant
        dominance_pruning_enabled = profile.dominance_pruning_enabled
        move_interning_enabled = profile.move_interning_enabled
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

        expanded_nodes = 0
        generated_nodes = 0
        stale_heap_pops = 0
        dominance_pruned = 0
        stats_probe = 0

        def finalize_run(solution_path, stop_reason: str, solution_cost: Optional[int] = None):
            stats["expanded_nodes"] = expanded_nodes
            stats["generated_nodes"] = generated_nodes
            stats["stale_heap_pops"] = stale_heap_pops
            stats["dominance_pruned"] = dominance_pruned
            stats["stop_reason"] = stop_reason
            stats["solution_length"] = 0 if solution_path is None else len(solution_path)
            if solution_cost is not None:
                stats["solution_cost"] = solution_cost

            frontier_size = len(frontier)
            visited_size = len(best_cost)
            state_cache_size = len(state_cache)
            if frontier_size > stats["peak_frontier_size"]:
                stats["peak_frontier_size"] = frontier_size
            if visited_size > stats["peak_visited_size"]:
                stats["peak_visited_size"] = visited_size
            if state_cache_size > stats["peak_state_cache_size"]:
                stats["peak_state_cache_size"] = state_cache_size

            self.last_run_stats = finalize_ucs_outcome(
                stats,
                started_at,
                solution_found=solution_path is not None,
                move_pool_size=len(move_pool),
                frontier_size=frontier_size,
                visited_size=visited_size,
                runtime_log_enabled=profile.runtime_log_enabled,
            )
            return solution_path

        while frontier:
            if should_cancel():
                return finalize_run(None, "cancelled")

            stats_probe += 1
            if stats_probe >= stats_update_interval:
                stats_probe = 0
                frontier_size = len(frontier)
                visited_size = len(best_cost)
                state_cache_size = len(state_cache)
                if frontier_size > stats["peak_frontier_size"]:
                    stats["peak_frontier_size"] = frontier_size
                if visited_size > stats["peak_visited_size"]:
                    stats["peak_visited_size"] = visited_size
                if state_cache_size > stats["peak_state_cache_size"]:
                    stats["peak_state_cache_size"] = state_cache_size

            cost, _, _, current_state_id = heappop(frontier)
            best_known_cost = best_cost.get(current_state_id)
            if best_known_cost is None or cost != best_known_cost:
                stale_heap_pops += 1
                continue

            current_node_index = best_node_index.get(current_state_id)
            if current_node_index is None:
                stale_heap_pops += 1
                continue

            current_state = state_cache.pop(current_state_id, None)
            if current_state is None:
                stale_heap_pops += 1
                continue

            expanded_nodes += 1

            if current_state.is_goal:
                path = reconstruct_interned_path(
                    current_node_index,
                    parent_index_arena,
                    edge_move_ids_arena,
                    move_pool,
                )
                return finalize_run(path, "solved", solution_cost=cost)

            incoming_edge_move_ids = edge_move_ids_arena[current_node_index]
            last_move = (
                move_pool[incoming_edge_move_ids[-1]]
                if incoming_edge_move_ids
                else None
            )
            candidate_moves = get_valid_moves(
                current_state,
                prune_safe=prune_safe_moves,
                last_move=last_move if prune_immediate_undo else None,
                prune_canonical_redundant=prune_canonical_redundant,
                sort_moves=sort_candidate_moves,
            )

            cancel_probe = 0
            for move in candidate_moves:
                cancel_probe += 1
                if cancel_probe >= inner_cancel_check_interval:
                    cancel_probe = 0
                    if should_cancel():
                        return finalize_run(None, "cancelled")

                next_state, forced_moves = apply_move_with_forced(current_state, move)
                edge_cost = ucs_move_cost(
                    move, prev_state=current_state, next_state=next_state
                )
                if forced_moves:
                    edge_cost += ucs_forced_foundation_chain_cost(
                        len(forced_moves)
                    )

                edge_moves = (move, *forced_moves)
                next_state_id = state_id(next_state)
                new_cost = cost + edge_cost
                generated_nodes += 1

                old_cost = best_cost.get(next_state_id)
                if (
                    dominance_pruning_enabled
                    and old_cost is not None
                    and new_cost >= old_cost
                ):
                    dominance_pruned += 1
                    continue

                if move_interning_enabled:
                    edge_move_ids = encode_edge_moves(
                        edge_moves, move_index_by_signature, move_pool
                    )
                else:
                    base_idx = len(move_pool)
                    move_pool.extend(edge_moves)
                    edge_move_ids = tuple(
                        range(base_idx, base_idx + len(edge_moves))
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

        return finalize_run(None, "exhausted")
