"""Utility helpers used by the BFS solver."""

from __future__ import annotations

from backend.experiments.solver_stats import SolverStats


def reconstruct_bfs_path(
    node_index: int, parent_index_arena: list, incoming_move_arena: list
) -> list:
    """Reconstruct a BFS path from parent and incoming-move arenas."""
    path = []
    walk = node_index
    while walk >= 0:
        move = incoming_move_arena[walk]
        if move is not None:
            path.append(move)
        walk = parent_index_arena[walk]
    path.reverse()
    return path


def finalize_bfs_outcome(
    stats: dict,
    started_at: float,
    solution_found: bool,
    frontier_size: int,
    visited_size: int,
    runtime_log_enabled: bool,
):
    """Finalize and optionally print BFS runtime stats."""
    stats["final_frontier_size"] = frontier_size
    stats["final_visited_size"] = visited_size
    finalized_stats = SolverStats.finalize_bfs(
        stats, started_at, solution_found=solution_found
    )
    if runtime_log_enabled:
        print(SolverStats.format_bfs(finalized_stats))
    return finalized_stats
