"""Shared helper functions for DFS runtime behavior and path handling."""

from __future__ import annotations

def reconstruct_edge_path(
    goal_index: int, parent_index_arena: list, edge_moves_arena: list
) -> list:
    """Reconstruct path by walking parent links and collecting edge move tuples."""
    path = []
    walk = goal_index
    while walk >= 0:
        edge_moves = edge_moves_arena[walk]
        if edge_moves:
            path.extend(reversed(edge_moves))
        walk = parent_index_arena[walk]
    path.reverse()
    return path
