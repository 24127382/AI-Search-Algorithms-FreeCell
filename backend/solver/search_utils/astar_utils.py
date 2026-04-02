"""Utility helpers used by the Weighted A* solver."""

from __future__ import annotations

from backend.experiments.solver_stats import SolverStats


def finalize_astar_outcome(
    stats: dict,
    started_at: float,
    solution_found: bool,
    move_pool_size: int,
    frontier_size: int,
    closed_size: int,
    runtime_log_enabled: bool,
):
    """Finalize and optionally print A* runtime stats."""
    stats["move_pool_size"] = move_pool_size
    stats["final_frontier_size"] = frontier_size
    stats["final_closed_size"] = closed_size
    finalized_stats = SolverStats.finalize_astar(
        stats, started_at, solution_found=solution_found
    )
    if runtime_log_enabled:
        print(SolverStats.format_astar(finalized_stats))
    return finalized_stats


def maybe_compact_astar_arena(
    parent_index_arena: list,
    edge_move_ids_arena: list,
    best_node_index: dict,
    stats: dict,
    compact_min_arena_nodes: int,
    compact_live_ratio: int,
) -> None:
    """Compact A* path arena when orphaned nodes dominate live nodes."""
    arena_size = len(parent_index_arena)
    if arena_size < compact_min_arena_nodes:
        return

    live_state_count = len(best_node_index)
    if arena_size <= live_state_count * compact_live_ratio:
        return

    live_indices = set()
    for node_index in best_node_index.values():
        walk = node_index
        while walk >= 0 and walk not in live_indices:
            live_indices.add(walk)
            walk = parent_index_arena[walk]

    if arena_size <= len(live_indices) * compact_live_ratio:
        return

    remap: dict = {}
    new_parent_index_arena: list = []
    new_edge_move_ids_arena: list = []

    for old_index in sorted(live_indices):
        remap[old_index] = len(new_parent_index_arena)
        new_parent_index_arena.append(parent_index_arena[old_index])
        new_edge_move_ids_arena.append(edge_move_ids_arena[old_index])

    for idx, old_parent in enumerate(new_parent_index_arena):
        new_parent_index_arena[idx] = remap.get(old_parent, -1)

    for state_board_id, old_index in list(best_node_index.items()):
        remapped_index = remap.get(old_index)
        if remapped_index is None:
            continue
        best_node_index[state_board_id] = remapped_index

    reclaimed = arena_size - len(new_parent_index_arena)
    parent_index_arena[:] = new_parent_index_arena
    edge_move_ids_arena[:] = new_edge_move_ids_arena
    stats["arena_compactions"] += 1
    stats["arena_nodes_reclaimed"] += reclaimed
