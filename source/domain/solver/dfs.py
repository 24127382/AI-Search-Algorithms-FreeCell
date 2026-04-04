"""Depth-First Search solver with plain baseline behavior."""

from __future__ import annotations

from time import perf_counter
from typing import Callable, List, Optional

from source.application.engine.engine import apply_move, get_valid_moves
from source.application.experiments.solver_stats import SolverStats
from source.domain.solver.search_utils.dfs_utils import (
    reconstruct_edge_path,
)
from source.domain.solver.search_utils.search_profile import DFSProfile


class DFSAlgorithm:
    """Depth-First Search solver."""

    def __init__(
        self,
        game_state,
        should_cancel: Optional[Callable] = None,
        profile: Optional[DFSProfile] = None,
        hard_time_cap_ms: Optional[float] = None,
        runtime_log_enabled: Optional[bool] = None,
    ):
        self.game_state = game_state
        self.should_cancel = should_cancel or (lambda: False)
        selected_profile = profile or DFSProfile.from_env()
        self.profile = selected_profile
        self.hard_time_cap_ms = (
            selected_profile.hard_time_cap_ms
            if hard_time_cap_ms is None
            else max(1.0, float(hard_time_cap_ms))
        )
        self.runtime_log_enabled = (
            selected_profile.runtime_log_enabled
            if runtime_log_enabled is None
            else bool(runtime_log_enabled)
        )
        self.last_run_stats = None

        # Backward-compatible public fields.
        self.expanded_nodes = 0
        self.peak_stack_size = 0
        self.execution_time_ms = 0.0

    def search(
        self,
        prefix_moves: tuple = (),
    ) -> Optional[List]:
        """Run DFS until solved, cancelled, exhausted, or time cap is reached."""
        started_at = perf_counter()
        should_cancel = self.should_cancel
        profile = self.profile
        inner_cancel_check_interval = profile.inner_cancel_check_interval
        stats_update_interval = profile.stats_update_interval
        finalize_dfs_fn = SolverStats.finalize_dfs
        format_dfs_fn = SolverStats.format_dfs

        root_state = self.game_state
        root_key = root_state.board_code

        state_arena = [root_state]
        parent_index_arena = [-1]
        edge_moves_arena = [()]
        stack = [0]
        visited = {root_key}

        self.expanded_nodes = 0
        self.peak_stack_size = 0

        stats = SolverStats.dfs_defaults()
        stats["peak_frontier_size"] = 1
        stats["peak_visited_size"] = 1

        expanded_nodes = 0
        generated_nodes = 0
        pruned_by_visited = 0
        stats_probe = 0

        def finalize_run(solution_path, stop_reason: str, timed_out: bool = False):
            stats["expanded_nodes"] = expanded_nodes
            stats["generated_nodes"] = generated_nodes
            stats["pruned_by_visited"] = pruned_by_visited
            if timed_out:
                stats["timed_out"] = True
            stats["stop_reason"] = stop_reason
            stats["solution_length"] = 0 if solution_path is None else len(solution_path)
            frontier_size = len(stack)
            visited_size = len(visited)
            stats["final_frontier_size"] = frontier_size
            stats["final_visited_size"] = visited_size

            if frontier_size > stats["peak_frontier_size"]:
                stats["peak_frontier_size"] = frontier_size
            if visited_size > stats["peak_visited_size"]:
                stats["peak_visited_size"] = visited_size

            self.last_run_stats = finalize_dfs_fn(
                stats, started_at, solution_found=solution_path is not None
            )
            self.execution_time_ms = stats["elapsed_ms"]
            self.expanded_nodes = stats.get("expanded_nodes", 0)
            self.peak_stack_size = stats.get("peak_frontier_size", 0)
            if self.runtime_log_enabled:
                print(format_dfs_fn(self.last_run_stats))
            return solution_path

        while stack:
            elapsed_ms = (perf_counter() - started_at) * 1000
            if elapsed_ms >= self.hard_time_cap_ms:
                return finalize_run(None, "hard_time_cap", timed_out=True)

            if should_cancel():
                return finalize_run(None, "cancelled")

            stats_probe += 1
            if stats_probe >= stats_update_interval:
                stats_probe = 0
                frontier_size = len(stack)
                visited_size = len(visited)
                if frontier_size > stats["peak_frontier_size"]:
                    stats["peak_frontier_size"] = frontier_size
                if visited_size > stats["peak_visited_size"]:
                    stats["peak_visited_size"] = visited_size

            node_index = stack.pop()
            state = state_arena[node_index]

            if state.is_goal:
                local_path = reconstruct_edge_path(
                    node_index, parent_index_arena, edge_moves_arena
                )
                return finalize_run(list(prefix_moves) + local_path, "solved")

            expanded_nodes += 1

            cancel_probe = 0
            for move in reversed(get_valid_moves(state)):
                cancel_probe += 1
                if cancel_probe >= inner_cancel_check_interval:
                    cancel_probe = 0
                    if should_cancel():
                        return finalize_run(None, "cancelled")

                new_state = apply_move(state, move)
                generated_nodes += 1
                new_state_key = new_state.board_code
                if new_state_key in visited:
                    pruned_by_visited += 1
                    continue

                visited.add(new_state_key)
                child_index = len(state_arena)
                state_arena.append(new_state)
                parent_index_arena.append(node_index)
                edge_moves_arena.append((move,))
                stack.append(child_index)

        return finalize_run(None, "exhausted")
