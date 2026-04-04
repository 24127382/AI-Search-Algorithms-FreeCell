"""Breadth-First Search solver using canonical State keys.

Visited-state detection uses each state's canonical board key when available,
which avoids hashing collisions in practical runs and aligns with `State`'s
cached identity model.
"""

from collections import deque
from time import perf_counter
from typing import Callable, Optional

from source.application.engine.engine import apply_move, get_valid_moves
from source.application.experiments.solver_stats import SolverStats
from source.domain.solver.search_utils.bfs_utils import (
    finalize_bfs_outcome,
    reconstruct_bfs_path,
)
from source.domain.solver.search_utils.search_profile import BFSProfile
from source.domain.solver.utils.utility import state_key


class BFSAlgorithm:
    """Breadth-First Search with canonical state-key deduplication."""

    def __init__(
        self,
        game_state,
        should_cancel: Optional[Callable] = None,
        profile: Optional[BFSProfile] = None,
    ):
        """Initialize BFS solver.

        Args:
            game_state: Initial board state.
            should_cancel: Optional callable returning True when solve should stop.
        """
        self.game_state = game_state
        self.should_cancel = should_cancel or (lambda: False)
        self.profile = profile or BFSProfile.from_env()
        self.last_run_stats = None

        # Backward-compatible public fields.
        self.expanded_nodes = 0
        self.peak_queue_size = 0
        self.execution_time_ms = 0.0

    def search(self):
        """Execute BFS search.

        Returns:
            list | None: Shortest path of moves, or None if unsolved.
        """
        started_at = perf_counter()
        should_cancel = self.should_cancel
        profile = self.profile
        inner_cancel_check_interval = profile.inner_cancel_check_interval
        stats_update_interval = profile.stats_update_interval
        runtime_log_enabled = profile.runtime_log_enabled
        hard_time_cap_ms = profile.hard_time_cap_ms
        max_expanded_nodes = profile.max_expanded_nodes

        start_state = self.game_state
        start_key = state_key(start_state)

        queue = deque([0])
        visited = {start_key}
        state_arena = [start_state]
        parent_index_arena = [-1]
        incoming_move_arena = [None]

        stats = SolverStats.bfs_defaults()
        stats["peak_frontier_size"] = 1
        stats["peak_visited_size"] = 1

        expanded_nodes = 0
        generated_nodes = 0
        pruned_by_visited = 0
        stats_probe = 0

        def finalize_run(solution_path, stop_reason: str):
            stats["expanded_nodes"] = expanded_nodes
            stats["generated_nodes"] = generated_nodes
            stats["pruned_by_visited"] = pruned_by_visited
            stats["stop_reason"] = stop_reason
            stats["solution_length"] = 0 if solution_path is None else len(solution_path)

            frontier_size = len(queue)
            visited_size = len(visited)
            if frontier_size > stats["peak_frontier_size"]:
                stats["peak_frontier_size"] = frontier_size
            if visited_size > stats["peak_visited_size"]:
                stats["peak_visited_size"] = visited_size

            self.last_run_stats = finalize_bfs_outcome(
                stats,
                started_at,
                solution_found=solution_path is not None,
                frontier_size=frontier_size,
                visited_size=visited_size,
                runtime_log_enabled=runtime_log_enabled,
            )
            self.execution_time_ms = stats["elapsed_ms"]
            self.expanded_nodes = stats.get("expanded_nodes", 0)
            self.peak_queue_size = stats.get("peak_frontier_size", 0)
            return solution_path

        while queue:
            if (perf_counter() - started_at) * 1000.0 >= hard_time_cap_ms:
                return finalize_run(None, "hard_time_cap")

            if should_cancel():
                return finalize_run(None, "cancelled")

            stats_probe += 1
            if stats_probe >= stats_update_interval:
                stats_probe = 0
                frontier_size = len(queue)
                visited_size = len(visited)
                if frontier_size > stats["peak_frontier_size"]:
                    stats["peak_frontier_size"] = frontier_size
                if visited_size > stats["peak_visited_size"]:
                    stats["peak_visited_size"] = visited_size

            node_index = queue.popleft()
            state = state_arena[node_index]

            expanded_nodes += 1

            if state.is_goal:
                path = reconstruct_bfs_path(
                    node_index, parent_index_arena, incoming_move_arena
                )
                return finalize_run(path, "solved")

            if expanded_nodes >= max_expanded_nodes:
                return finalize_run(None, "expanded_limit")

            cancel_probe = 0
            for move in get_valid_moves(state):
                cancel_probe += 1
                if cancel_probe >= inner_cancel_check_interval:
                    cancel_probe = 0
                    if should_cancel():
                        return finalize_run(None, "cancelled")
                    if (perf_counter() - started_at) * 1000.0 >= hard_time_cap_ms:
                        return finalize_run(None, "hard_time_cap")

                new_state = apply_move(state, move)
                generated_nodes += 1

                new_key = state_key(new_state)
                if new_key in visited:
                    pruned_by_visited += 1
                    continue

                visited.add(new_key)
                child_index = len(state_arena)
                state_arena.append(new_state)
                parent_index_arena.append(node_index)
                incoming_move_arena.append(move)
                queue.append(child_index)

        return finalize_run(None, "exhausted")
