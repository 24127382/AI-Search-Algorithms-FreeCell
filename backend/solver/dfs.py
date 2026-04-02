"""Depth-First Search solver and DFS optimization toolkit.

This module provides:
- Single-profile DFS with path-arena parent pointers.
- K-step cycle pruning.
- Progressive widening with conservative defaults.
- Optional move canonicalization (state canonicalization remains primary).
- Optional delayed duplicate detection (default off; enable only after profiling).
"""

from __future__ import annotations

from time import perf_counter
from typing import Callable, List, Optional

from backend.engine.engine import apply_move_with_forced, get_valid_moves
from backend.experiments.solver_stats import SolverStats
from backend.solver.search_utils.dfs_utils import (
    accept_candidate,
    allowed_children_count,
    build_full_solution_path,
    default_hard_time_cap_ms,
    default_improvement_budget_ms,
    edge_signature,
    flush_pending_candidates,
    has_best_solution,
)
from backend.solver.search_utils.dfs_utils import (
    runtime_log_enabled as dfs_runtime_log_enabled,
)
from backend.solver.search_utils.search_profile import DFSProfile
from backend.solver.utils.utility import state_key


class DFSAlgorithm:
    """Depth-First Search solver with optimization profiles."""

    def __init__(
        self,
        game_state,
        should_cancel: Optional[Callable] = None,
        profile: Optional[DFSProfile] = None,
        improvement_budget_ms: Optional[float] = None,
        hard_time_cap_ms: Optional[float] = None,
        runtime_log_enabled: Optional[bool] = None,
    ):
        self.game_state = game_state
        self.should_cancel = should_cancel or (lambda: False)
        self.profile = profile or DFSProfile.from_env()
        self.improvement_budget_ms = (
            default_improvement_budget_ms()
            if improvement_budget_ms is None
            else max(0.0, float(improvement_budget_ms))
        )
        self.hard_time_cap_ms = (
            default_hard_time_cap_ms()
            if hard_time_cap_ms is None
            else max(1.0, float(hard_time_cap_ms))
        )
        self.runtime_log_enabled = (
            dfs_runtime_log_enabled()
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
        """Run DFS with the current profile."""
        started_at = perf_counter()
        profile = self.profile

        root_state = self.game_state
        root_depth = len(prefix_moves)
        root_key = state_key(root_state)

        state_arena = [root_state]
        parent_index_arena = [-1]
        edge_moves_arena = [()]
        depth_arena = [root_depth]
        incoming_last_move_arena = [prefix_moves[-1] if prefix_moves else None]
        if profile.k_cycle_steps > 0:
            recent_hashes_arena = [tuple([root_key])]
        else:
            recent_hashes_arena = [()]

        stack = [0]
        best_depth_by_state = {root_key: root_depth}
        best_solution_node_index = None
        best_solution_parent_index = None
        best_solution_edge_moves = ()
        best_solution_len = float("inf")
        first_solution_at_ms = None

        self.expanded_nodes = 0
        self.peak_stack_size = 0

        stats = SolverStats.dfs_defaults(profile.delayed_duplicate_detection)

        while stack:
            elapsed_ms = (perf_counter() - started_at) * 1000
            if elapsed_ms >= self.hard_time_cap_ms:
                stats["timed_out"] = True
                stats["stop_reason"] = "hard_time_cap"
                if has_best_solution(
                    best_solution_node_index, best_solution_parent_index
                ):
                    full_path = build_full_solution_path(
                        prefix_moves,
                        best_solution_node_index,
                        best_solution_parent_index,
                        best_solution_edge_moves,
                        parent_index_arena,
                        edge_moves_arena,
                    )
                    if full_path is not None:
                        if stats["stop_reason"] == "running":
                            stats["stop_reason"] = "solved"
                        stats["solution_length"] = len(full_path)
                        stats["final_frontier_size"] = len(stack)
                        stats["final_visited_size"] = len(best_depth_by_state)
                        self.last_run_stats = SolverStats.finalize_dfs(
                            stats, started_at, solution_found=True
                        )
                        self.execution_time_ms = stats["elapsed_ms"]
                        self.expanded_nodes = stats.get("expanded_nodes", 0)
                        self.peak_stack_size = stats.get("peak_frontier_size", 0)
                        if self.runtime_log_enabled:
                            print(SolverStats.format_dfs(self.last_run_stats))
                        return full_path

                stats["solution_length"] = 0
                stats["final_frontier_size"] = len(stack)
                stats["final_visited_size"] = len(best_depth_by_state)
                self.last_run_stats = SolverStats.finalize_dfs(
                    stats, started_at, solution_found=False
                )
                self.execution_time_ms = stats["elapsed_ms"]
                self.expanded_nodes = stats.get("expanded_nodes", 0)
                self.peak_stack_size = stats.get("peak_frontier_size", 0)
                if self.runtime_log_enabled:
                    print(SolverStats.format_dfs(self.last_run_stats))
                return None

            if self.should_cancel():
                if has_best_solution(
                    best_solution_node_index, best_solution_parent_index
                ):
                    stats["stop_reason"] = "cancelled_with_best"
                    full_path = build_full_solution_path(
                        prefix_moves,
                        best_solution_node_index,
                        best_solution_parent_index,
                        best_solution_edge_moves,
                        parent_index_arena,
                        edge_moves_arena,
                    )
                    if full_path is not None:
                        stats["solution_length"] = len(full_path)
                        stats["final_frontier_size"] = len(stack)
                        stats["final_visited_size"] = len(best_depth_by_state)
                        self.last_run_stats = SolverStats.finalize_dfs(
                            stats, started_at, solution_found=True
                        )
                        self.execution_time_ms = stats["elapsed_ms"]
                        self.expanded_nodes = stats.get("expanded_nodes", 0)
                        self.peak_stack_size = stats.get("peak_frontier_size", 0)
                        if self.runtime_log_enabled:
                            print(SolverStats.format_dfs(self.last_run_stats))
                        return full_path

                stats["solution_length"] = 0
                stats["stop_reason"] = "cancelled"
                stats["final_frontier_size"] = len(stack)
                stats["final_visited_size"] = len(best_depth_by_state)
                self.last_run_stats = SolverStats.finalize_dfs(
                    stats, started_at, solution_found=False
                )
                self.execution_time_ms = stats["elapsed_ms"]
                self.expanded_nodes = stats.get("expanded_nodes", 0)
                self.peak_stack_size = stats.get("peak_frontier_size", 0)
                if self.runtime_log_enabled:
                    print(SolverStats.format_dfs(self.last_run_stats))
                return None

            if (
                has_best_solution(best_solution_node_index, best_solution_parent_index)
                and first_solution_at_ms is not None
            ):
                elapsed_ms = (perf_counter() - started_at) * 1000
                if elapsed_ms - first_solution_at_ms >= self.improvement_budget_ms:
                    stats["stop_reason"] = "improvement_budget_exhausted"
                    full_path = build_full_solution_path(
                        prefix_moves,
                        best_solution_node_index,
                        best_solution_parent_index,
                        best_solution_edge_moves,
                        parent_index_arena,
                        edge_moves_arena,
                    )
                    if full_path is not None:
                        stats["solution_length"] = len(full_path)
                        stats["final_frontier_size"] = len(stack)
                        stats["final_visited_size"] = len(best_depth_by_state)
                        self.last_run_stats = SolverStats.finalize_dfs(
                            stats, started_at, solution_found=True
                        )
                        self.execution_time_ms = stats["elapsed_ms"]
                        self.expanded_nodes = stats.get("expanded_nodes", 0)
                        self.peak_stack_size = stats.get("peak_frontier_size", 0)
                        if self.runtime_log_enabled:
                            print(SolverStats.format_dfs(self.last_run_stats))
                        return full_path

            if len(stack) > stats["peak_frontier_size"]:
                stats["peak_frontier_size"] = len(stack)
            if len(best_depth_by_state) > stats["peak_visited_size"]:
                stats["peak_visited_size"] = len(best_depth_by_state)

            node_index = stack.pop()
            state = state_arena[node_index]
            current_key = state_key(state)
            node_depth = depth_arena[node_index]
            last_move = incoming_last_move_arena[node_index]

            if node_depth >= best_solution_len:
                stats["pruned_by_bound"] += 1
                continue

            best_known_depth = best_depth_by_state.get(current_key)
            if best_known_depth is not None and node_depth > best_known_depth:
                stats["stale_stack_pops"] += 1
                continue

            stats["expanded_nodes"] += 1

            if state.is_goal:
                if node_depth < best_solution_len:
                    best_solution_node_index = node_index
                    best_solution_parent_index = None
                    best_solution_edge_moves = ()
                    best_solution_len = node_depth
                    stats["best_solution_updates"] += 1
                    stats["solution_length"] = node_depth
                    if first_solution_at_ms is None:
                        first_solution_at_ms = (perf_counter() - started_at) * 1000
                continue

            valid_moves = get_valid_moves(
                state,
                last_move=last_move,
                prune_canonical_redundant=True,
            )
            allowed_count = allowed_children_count(
                node_depth, len(valid_moves), profile
            )
            if allowed_count < len(valid_moves):
                stats["pruned_by_widening"] += len(valid_moves) - allowed_count
            valid_moves = valid_moves[:allowed_count]

            seen_edge_signatures = set()
            pending = []
            insertion_order = 0

            for move in reversed(valid_moves):
                if self.should_cancel():
                    if has_best_solution(
                        best_solution_node_index, best_solution_parent_index
                    ):
                        stats["stop_reason"] = "cancelled_with_best"
                        full_path = build_full_solution_path(
                            prefix_moves,
                            best_solution_node_index,
                            best_solution_parent_index,
                            best_solution_edge_moves,
                            parent_index_arena,
                            edge_moves_arena,
                        )
                        if full_path is not None:
                            stats["solution_length"] = len(full_path)
                            stats["final_frontier_size"] = len(stack)
                            stats["final_visited_size"] = len(best_depth_by_state)
                            self.last_run_stats = SolverStats.finalize_dfs(
                                stats, started_at, solution_found=True
                            )
                            self.execution_time_ms = stats["elapsed_ms"]
                            self.expanded_nodes = stats.get("expanded_nodes", 0)
                            self.peak_stack_size = stats.get("peak_frontier_size", 0)
                            if self.runtime_log_enabled:
                                print(SolverStats.format_dfs(self.last_run_stats))
                            return full_path

                    stats["solution_length"] = 0
                    stats["stop_reason"] = "cancelled"
                    stats["final_frontier_size"] = len(stack)
                    stats["final_visited_size"] = len(best_depth_by_state)
                    self.last_run_stats = SolverStats.finalize_dfs(
                        stats, started_at, solution_found=False
                    )
                    self.execution_time_ms = stats["elapsed_ms"]
                    self.expanded_nodes = stats.get("expanded_nodes", 0)
                    self.peak_stack_size = stats.get("peak_frontier_size", 0)
                    if self.runtime_log_enabled:
                        print(SolverStats.format_dfs(self.last_run_stats))
                    return None

                new_state, forced_moves = apply_move_with_forced(state, move)
                edge_moves = (move, *forced_moves)
                next_depth = node_depth + len(edge_moves)
                stats["generated_nodes"] += 1

                if next_depth >= best_solution_len:
                    stats["pruned_by_bound"] += 1
                    continue

                new_state_key = state_key(new_state)

                if profile.k_cycle_steps > 0:
                    recent = recent_hashes_arena[node_index]
                    if new_state_key in recent:
                        stats["pruned_by_cycle"] += 1
                        continue

                if profile.move_canonicalization:
                    signature = edge_signature(edge_moves)
                    if signature in seen_edge_signatures:
                        stats["pruned_by_canonical"] += 1
                        continue
                    seen_edge_signatures.add(signature)

                candidate = {
                    "order": insertion_order,
                    "state": new_state,
                    "state_hash": new_state_key,
                    "depth": next_depth,
                    "edge_moves": edge_moves,
                    "is_goal": bool(new_state.is_goal),
                }
                insertion_order += 1

                if profile.delayed_duplicate_detection:
                    pending.append(candidate)
                    if len(pending) >= profile.delayed_duplicate_batch_size:
                        for item in flush_pending_candidates(pending, stats):
                            (
                                best_solution_node_index,
                                best_solution_parent_index,
                                best_solution_edge_moves,
                                best_solution_len,
                                first_solution_at_ms,
                            ) = accept_candidate(
                                item,
                                node_index,
                                profile,
                                started_at,
                                best_depth_by_state,
                                stats,
                                state_arena,
                                parent_index_arena,
                                edge_moves_arena,
                                depth_arena,
                                incoming_last_move_arena,
                                recent_hashes_arena,
                                stack,
                                best_solution_node_index,
                                best_solution_parent_index,
                                best_solution_edge_moves,
                                best_solution_len,
                                first_solution_at_ms,
                            )
                else:
                    (
                        best_solution_node_index,
                        best_solution_parent_index,
                        best_solution_edge_moves,
                        best_solution_len,
                        first_solution_at_ms,
                    ) = accept_candidate(
                        candidate,
                        node_index,
                        profile,
                        started_at,
                        best_depth_by_state,
                        stats,
                        state_arena,
                        parent_index_arena,
                        edge_moves_arena,
                        depth_arena,
                        incoming_last_move_arena,
                        recent_hashes_arena,
                        stack,
                        best_solution_node_index,
                        best_solution_parent_index,
                        best_solution_edge_moves,
                        best_solution_len,
                        first_solution_at_ms,
                    )

            if profile.delayed_duplicate_detection:
                for item in flush_pending_candidates(pending, stats):
                    (
                        best_solution_node_index,
                        best_solution_parent_index,
                        best_solution_edge_moves,
                        best_solution_len,
                        first_solution_at_ms,
                    ) = accept_candidate(
                        item,
                        node_index,
                        profile,
                        started_at,
                        best_depth_by_state,
                        stats,
                        state_arena,
                        parent_index_arena,
                        edge_moves_arena,
                        depth_arena,
                        incoming_last_move_arena,
                        recent_hashes_arena,
                        stack,
                        best_solution_node_index,
                        best_solution_parent_index,
                        best_solution_edge_moves,
                        best_solution_len,
                        first_solution_at_ms,
                    )

        if has_best_solution(best_solution_node_index, best_solution_parent_index):
            stats["stop_reason"] = "exhausted_with_solution"
            full_path = build_full_solution_path(
                prefix_moves,
                best_solution_node_index,
                best_solution_parent_index,
                best_solution_edge_moves,
                parent_index_arena,
                edge_moves_arena,
            )
            if full_path is not None:
                stats["solution_length"] = len(full_path)
                stats["final_frontier_size"] = len(stack)
                stats["final_visited_size"] = len(best_depth_by_state)
                self.last_run_stats = SolverStats.finalize_dfs(
                    stats, started_at, solution_found=True
                )
                self.execution_time_ms = stats["elapsed_ms"]
                self.expanded_nodes = stats.get("expanded_nodes", 0)
                self.peak_stack_size = stats.get("peak_frontier_size", 0)
                if self.runtime_log_enabled:
                    print(SolverStats.format_dfs(self.last_run_stats))
                return full_path

        stats["solution_length"] = 0
        stats["stop_reason"] = "exhausted_no_solution"
        stats["final_frontier_size"] = len(stack)
        stats["final_visited_size"] = len(best_depth_by_state)
        self.last_run_stats = SolverStats.finalize_dfs(
            stats, started_at, solution_found=False
        )
        self.execution_time_ms = stats["elapsed_ms"]
        self.expanded_nodes = stats.get("expanded_nodes", 0)
        self.peak_stack_size = stats.get("peak_frontier_size", 0)
        if self.runtime_log_enabled:
            print(SolverStats.format_dfs(self.last_run_stats))
        return None
