"""Breadth-First Search solver using canonical State keys.

Visited-state detection uses each state's canonical board key when available,
which avoids hashing collisions in practical runs and aligns with `State`'s
cached identity model.
"""

from collections import deque
from time import perf_counter
from typing import Callable, Optional

from backend.engine.engine import apply_move, get_valid_moves
from backend.experiments.solver_stats import SolverStats
from backend.solver.search_utils.bfs_utils import (
    finalize_bfs_outcome,
    reconstruct_bfs_path,
)
from backend.solver.utils.utility import env_zero_is_false, state_key

BFS_RUNTIME_LOG_ENABLED = env_zero_is_false("BFS_RUNTIME_LOG", default=True)


class BFSAlgorithm:
    """Breadth-First Search with canonical state-key deduplication."""

    def __init__(self, game_state, should_cancel: Optional[Callable] = None):
        """Initialize BFS solver.

        Args:
            game_state: Initial board state.
            should_cancel: Optional callable returning True when solve should stop.
        """
        self.game_state = game_state
        self.should_cancel = should_cancel or (lambda: False)
        self.last_run_stats = None

        # Backward-compatible public fields.
        self.expanded_nodes = 0
        self.peak_queue_size = 0
        self.execution_time_ms = 0.0

    def search(self):
        """Execute BFS search with canonical state-key deduplication.

        Returns:
            list | None: Shortest path of moves, or None if unsolved.
        """
        started_at = perf_counter()

        start_state = self.game_state
        start_key = state_key(start_state)

        queue = deque([0])
        visited = {start_key}
        state_arena = [start_state]
        parent_index_arena = [-1]
        incoming_move_arena = [None]

        stats = SolverStats.bfs_defaults()
        stats["peak_visited_size"] = 1

        while queue:
            if self.should_cancel():
                stats["stop_reason"] = "cancelled"
                stats["solution_length"] = 0
                self.last_run_stats = finalize_bfs_outcome(
                    stats,
                    started_at,
                    solution_found=False,
                    frontier_size=len(queue),
                    visited_size=len(visited),
                    runtime_log_enabled=BFS_RUNTIME_LOG_ENABLED,
                )
                self.execution_time_ms = stats["elapsed_ms"]
                self.expanded_nodes = stats.get("expanded_nodes", 0)
                self.peak_queue_size = stats.get("peak_frontier_size", 0)
                return None

            if len(queue) > stats["peak_frontier_size"]:
                stats["peak_frontier_size"] = len(queue)
            if len(visited) > stats["peak_visited_size"]:
                stats["peak_visited_size"] = len(visited)

            node_index = queue.popleft()
            state = state_arena[node_index]

            stats["expanded_nodes"] += 1

            if state.is_goal:
                path = reconstruct_bfs_path(
                    node_index, parent_index_arena, incoming_move_arena
                )
                stats["stop_reason"] = "solved"
                stats["solution_length"] = len(path)
                self.last_run_stats = finalize_bfs_outcome(
                    stats,
                    started_at,
                    solution_found=True,
                    frontier_size=len(queue),
                    visited_size=len(visited),
                    runtime_log_enabled=BFS_RUNTIME_LOG_ENABLED,
                )
                self.execution_time_ms = stats["elapsed_ms"]
                self.expanded_nodes = stats.get("expanded_nodes", 0)
                self.peak_queue_size = stats.get("peak_frontier_size", 0)
                return path

            for move in get_valid_moves(state, prune_canonical_redundant=True):
                if self.should_cancel():
                    stats["stop_reason"] = "cancelled"
                    stats["solution_length"] = 0
                    self.last_run_stats = finalize_bfs_outcome(
                        stats,
                        started_at,
                        solution_found=False,
                        frontier_size=len(queue),
                        visited_size=len(visited),
                        runtime_log_enabled=BFS_RUNTIME_LOG_ENABLED,
                    )
                    self.execution_time_ms = stats["elapsed_ms"]
                    self.expanded_nodes = stats.get("expanded_nodes", 0)
                    self.peak_queue_size = stats.get("peak_frontier_size", 0)
                    return None

                new_state = apply_move(state, move)
                stats["generated_nodes"] += 1

                new_key = state_key(new_state)
                if new_key in visited:
                    stats["pruned_by_visited"] += 1
                    continue

                visited.add(new_key)
                child_index = len(state_arena)
                state_arena.append(new_state)
                parent_index_arena.append(node_index)
                incoming_move_arena.append(move)
                queue.append(child_index)

        stats["stop_reason"] = "exhausted"
        stats["solution_length"] = 0
        self.last_run_stats = finalize_bfs_outcome(
            stats,
            started_at,
            solution_found=False,
            frontier_size=len(queue),
            visited_size=len(visited),
            runtime_log_enabled=BFS_RUNTIME_LOG_ENABLED,
        )
        self.execution_time_ms = stats["elapsed_ms"]
        self.expanded_nodes = stats.get("expanded_nodes", 0)
        self.peak_queue_size = stats.get("peak_frontier_size", 0)
        return None
