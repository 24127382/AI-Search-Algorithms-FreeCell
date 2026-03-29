"""Breadth-First Search solver with runtime stats and logging."""

import os
from collections import deque
from time import perf_counter
from typing import Callable, List, Optional

from backend.engine.engine import apply_move, get_valid_moves


BFS_RUNTIME_LOG_ENABLED = os.environ.get("BFS_RUNTIME_LOG", "1") != "0"


class BFSAlgorithm:
    """Breadth-first solver using Zobrist hashing for visited state tracking."""

    def __init__(self, game_state, should_cancel: Optional[Callable] = None):
        """Store initial game state for BFS search.

        Args:
            game_state: Initial board state.
            should_cancel: Optional callable returning True when solve should stop.
        """
        self.game_state = game_state
        self.should_cancel = should_cancel or (lambda: False)
        self.last_run_stats = None

    def _finalize_stats(self, stats: dict, started_at: float, solution_found: bool) -> None:
        """Finalize and persist run statistics.

        Args:
            stats: Mutable stats dictionary.
            started_at: Run start timestamp from perf_counter().
            solution_found: Whether run found a valid solution path.
        """
        stats["elapsed_ms"] = (perf_counter() - started_at) * 1000
        stats["solution_found"] = solution_found
        expanded_nodes = max(stats.get("expanded_nodes", 0), 1)
        generated_nodes = stats.get("generated_nodes", 0)
        pruned_by_visited = stats.get("pruned_by_visited", 0)
        stats["effective_branching_factor"] = generated_nodes / expanded_nodes
        stats["visited_prune_rate"] = pruned_by_visited / max(generated_nodes, 1)
        self.last_run_stats = stats

    def format_last_run_stats(self) -> str:
        """Build a compact human-readable report for last_run_stats.

        Returns:
            str: Multiline summary string.
        """
        if not self.last_run_stats:
            return "No BFS stats available. Run search() first."

        stats = self.last_run_stats

        lines = [
            "BFS Run Stats",
            f"- solution_found: {stats.get('solution_found', False)}",
            f"- elapsed_ms: {stats.get('elapsed_ms', 0.0):.2f}",
            f"- solution_length: {stats.get('solution_length', 0)}",
            f"- expanded_nodes: {stats.get('expanded_nodes', 0)}",
            f"- generated_nodes: {stats.get('generated_nodes', 0)}",
            f"- stale_queue_pops: {stats.get('stale_queue_pops', 0)}",
            f"- pruned_by_visited: {stats.get('pruned_by_visited', 0)}",
            f"- visited_prune_rate: {stats.get('visited_prune_rate', 0.0):.2%}",
            f"- effective_branching_factor: {stats.get('effective_branching_factor', 0.0):.3f}",
            f"- peak_frontier_size: {stats.get('peak_frontier_size', 0)}",
            f"- peak_visited_size: {stats.get('peak_visited_size', 0)}",
            f"- final_frontier_size: {stats.get('final_frontier_size', 0)}",
            f"- final_visited_size: {stats.get('final_visited_size', 0)}",
        ]
        return "\n".join(lines)

    def _log_progress(self) -> None:
        """Print full runtime summary after a BFS run ends."""
        print(self.format_last_run_stats())

    def search(self) -> Optional[List]:
        """Execute BFS search using Zobrist hashing for memory efficiency.

        Uses Zobrist hashing (64-bit integers) instead of storing full state
        objects in visited set, significantly reducing memory consumption.

        Returns:
            list | None: Path of moves from start to goal, or None if unsolved.
        """
        started_at = perf_counter()
        queue = deque([(self.game_state, [])])
        visited = set()

        stats = {
            "expanded_nodes": 0,
            "generated_nodes": 0,
            "stale_queue_pops": 0,
            "pruned_by_visited": 0,
            "peak_frontier_size": 1,
            "peak_visited_size": 0,
            "solution_length": 0,
        }

        while queue:
            if self.should_cancel():
                return None

            if len(queue) > stats["peak_frontier_size"]:
                stats["peak_frontier_size"] = len(queue)
            if len(visited) > stats["peak_visited_size"]:
                stats["peak_visited_size"] = len(visited)

            state, path = queue.popleft()
            state_hash = hash(state)  # Zobrist hash from State.__hash__()

            if state_hash in visited:
                stats["stale_queue_pops"] += 1
                continue

            visited.add(state_hash)
            stats["expanded_nodes"] += 1

            if state.is_goal:
                stats["solution_length"] = len(path)
                stats["final_frontier_size"] = len(queue)
                stats["final_visited_size"] = len(visited)
                self._finalize_stats(stats, started_at, solution_found=True)
                if BFS_RUNTIME_LOG_ENABLED:
                    self._log_progress()
                return path

            valid_moves = get_valid_moves(state)
            for move in valid_moves:
                if self.should_cancel():
                    return None

                new_state = apply_move(state, move)
                stats["generated_nodes"] += 1
                new_state_hash = hash(new_state)

                if new_state_hash in visited:
                    stats["pruned_by_visited"] += 1
                    continue

                queue.append((new_state, path + [move]))

        stats["final_frontier_size"] = len(queue)
        stats["final_visited_size"] = len(visited)
        self._finalize_stats(stats, started_at, solution_found=False)
        if BFS_RUNTIME_LOG_ENABLED:
            self._log_progress()
        return None