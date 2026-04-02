"""Shared helper functions for DFS runtime behavior and path handling."""

from __future__ import annotations

from time import perf_counter

from backend.solver.search_utils.search_profile import DFSProfile
from backend.solver.search_utils.ucs_utils import move_signature
from backend.solver.utils.utility import env_float, env_zero_is_false


def runtime_log_enabled() -> bool:
    """Return whether DFS runtime logging is enabled via environment."""
    return env_zero_is_false("DFS_RUNTIME_LOG", default=True)


def default_improvement_budget_ms() -> float:
    """Return configured DFS post-first-solution improvement budget in ms."""
    return env_float("DFS_IMPROVEMENT_BUDGET_MS", 400.0, minimum=0.0)


def default_hard_time_cap_ms() -> float:
    """Return configured hard DFS wall-clock cap in ms."""
    return env_float("DFS_HARD_TIME_CAP_MS", 30000.0, minimum=1.0)


def edge_signature(edge_moves: tuple) -> tuple:
    """Build canonical signature for a sequence of edge moves."""
    return tuple(move_signature(move) for move in edge_moves)


def allowed_children_count(depth: int, move_count: int, profile: DFSProfile) -> int:
    """Compute DFS branching cap under progressive widening settings."""
    if move_count <= 0:
        return 0
    if not profile.progressive_widening or depth < profile.widen_start_depth:
        return move_count

    # Decrease allowed width as depth grows to control deep branching explosion.
    allowed = int(
        profile.widen_base_width
        - (depth - profile.widen_start_depth) * profile.widen_growth
    )
    return min(move_count, max(1, allowed))


def accept_candidate(
    candidate: dict,
    parent_index: int,
    profile: DFSProfile,
    started_at: float,
    best_depth_by_state: dict,
    stats: dict,
    state_arena: list,
    parent_index_arena: list,
    edge_moves_arena: list,
    depth_arena: list,
    incoming_last_move_arena: list,
    recent_hashes_arena: list,
    stack: list,
    best_solution_node_index,
    best_solution_parent_index,
    best_solution_edge_moves: tuple,
    best_solution_len: float,
    first_solution_at_ms: float | None,
):
    """Accept one generated DFS candidate into solution tracker or frontier."""
    candidate_hash = candidate["state_hash"]
    candidate_depth = candidate["depth"]
    old_depth = best_depth_by_state.get(candidate_hash)
    if old_depth is not None and candidate_depth >= old_depth:
        stats["pruned_by_visited"] += 1
        return (
            best_solution_node_index,
            best_solution_parent_index,
            best_solution_edge_moves,
            best_solution_len,
            first_solution_at_ms,
        )

    best_depth_by_state[candidate_hash] = candidate_depth

    # Goal candidates don't need full arena slots; parent+edge is enough for path reconstruction.
    if candidate["is_goal"]:
        if candidate_depth < best_solution_len:
            best_solution_node_index = None
            best_solution_parent_index = parent_index
            best_solution_edge_moves = candidate["edge_moves"]
            best_solution_len = candidate_depth
            stats["best_solution_updates"] += 1
            stats["solution_length"] = candidate_depth
            if first_solution_at_ms is None:
                first_solution_at_ms = (perf_counter() - started_at) * 1000
        return (
            best_solution_node_index,
            best_solution_parent_index,
            best_solution_edge_moves,
            best_solution_len,
            first_solution_at_ms,
        )

    child_index = len(state_arena)
    state_arena.append(candidate["state"])
    parent_index_arena.append(parent_index)
    edge_moves_arena.append(candidate["edge_moves"])
    depth_arena.append(candidate_depth)
    incoming_last_move_arena.append(candidate["edge_moves"][-1])

    if profile.k_cycle_steps > 0:
        parent_recent = recent_hashes_arena[parent_index]
        next_recent = parent_recent + (candidate_hash,)
        recent_hashes_arena.append(next_recent[-profile.k_cycle_steps :])
    else:
        recent_hashes_arena.append(())

    stack.append(child_index)

    return (
        best_solution_node_index,
        best_solution_parent_index,
        best_solution_edge_moves,
        best_solution_len,
        first_solution_at_ms,
    )


def flush_pending_candidates(pending: list, stats: dict) -> list[dict]:
    """Deduplicate one mini-batch and return candidates in insertion order."""
    if not pending:
        return []

    best_by_hash = {}
    for item in pending:
        existing = best_by_hash.get(item["state_hash"])
        if existing is None:
            best_by_hash[item["state_hash"]] = item
            continue

        stats["pruned_by_mini_batch_duplicate"] += 1
        if item["depth"] < existing["depth"]:
            best_by_hash[item["state_hash"]] = item
        elif item["depth"] == existing["depth"] and item["order"] > existing["order"]:
            best_by_hash[item["state_hash"]] = item

    selected = sorted(best_by_hash.values(), key=lambda x: x["order"])
    pending.clear()
    return selected


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


def has_best_solution(best_solution_node_index, best_solution_parent_index) -> bool:
    """Return True when DFS currently stores any best-solution pointer."""
    return (
        best_solution_node_index is not None or best_solution_parent_index is not None
    )


def build_full_solution_path(
    prefix_moves: tuple,
    best_solution_node_index,
    best_solution_parent_index,
    best_solution_edge_moves: tuple,
    parent_index_arena: list,
    edge_moves_arena: list,
):
    """Build full solution path from DFS best-solution pointers."""
    if best_solution_node_index is not None:
        local_path = reconstruct_edge_path(
            best_solution_node_index, parent_index_arena, edge_moves_arena
        )
    elif best_solution_parent_index is not None:
        local_path = reconstruct_edge_path(
            best_solution_parent_index, parent_index_arena, edge_moves_arena
        )
        local_path.extend(best_solution_edge_moves)
    else:
        return None

    return list(prefix_moves) + local_path
