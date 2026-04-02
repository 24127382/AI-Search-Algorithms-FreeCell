"""Centralized runtime stats helpers for search algorithms.

This module keeps algorithm-specific stats schema, finalization logic, and
report formatting in one place so solver implementations stay focused on
search behavior.
"""

from __future__ import annotations

from time import perf_counter
from typing import Optional


class SolverStats:
    """Utility methods for BFS/DFS/A*/UCS stats lifecycle."""

    @staticmethod
    def bfs_defaults() -> dict:
        return {
            "expanded_nodes": 0,
            "generated_nodes": 0,
            "stale_queue_pops": 0,
            "pruned_by_visited": 0,
            "peak_frontier_size": 1,
            "peak_visited_size": 0,
            "solution_length": 0,
            "stop_reason": "running",
        }

    @staticmethod
    def dfs_defaults(delayed_duplicate_enabled: bool) -> dict:
        return {
            "expanded_nodes": 0,
            "generated_nodes": 0,
            "stale_stack_pops": 0,
            "pruned_by_visited": 0,
            "pruned_by_bound": 0,
            "pruned_by_cycle": 0,
            "pruned_by_widening": 0,
            "pruned_by_canonical": 0,
            "pruned_by_mini_batch_duplicate": 0,
            "peak_frontier_size": 1,
            "peak_visited_size": 1,
            "solution_length": 0,
            "best_solution_updates": 0,
            "delayed_duplicate_enabled": delayed_duplicate_enabled,
            "timed_out": False,
            "stop_reason": "running",
            "mode": "single",
        }

    @staticmethod
    def astar_defaults(weight: float) -> dict:
        return {
            "weight": weight,
            "expanded_nodes": 0,
            "generated_nodes": 0,
            "stale_heap_pops": 0,
            "pruned_by_cost": 0,
            "pruned_by_closed": 0,
            "reopened_nodes": 0,
            "arena_compactions": 0,
            "arena_nodes_reclaimed": 0,
            "peak_frontier_size": 1,
            "peak_g_cost_size": 1,
            "peak_closed_size": 0,
            "move_pool_size": 0,
            "solution_cost": None,
            "solution_length": 0,
            "stop_reason": "running",
        }

    @staticmethod
    def ucs_defaults() -> dict:
        return {
            "expanded_nodes": 0,
            "generated_nodes": 0,
            "stale_heap_pops": 0,
            "dominance_pruned": 0,
            "peak_frontier_size": 1,
            "peak_visited_size": 1,
            "peak_state_cache_size": 1,
            "move_pool_size": 0,
            "solution_cost": None,
            "solution_length": 0,
            "stop_reason": "running",
        }

    @staticmethod
    def finalize_bfs(stats: dict, started_at: float, solution_found: bool) -> dict:
        stats["elapsed_ms"] = (perf_counter() - started_at) * 1000
        stats["solution_found"] = solution_found
        expanded_nodes = max(stats.get("expanded_nodes", 0), 1)
        generated_nodes = stats.get("generated_nodes", 0)
        pruned_by_visited = stats.get("pruned_by_visited", 0)
        stats["effective_branching_factor"] = generated_nodes / expanded_nodes
        stats["visited_prune_rate"] = pruned_by_visited / max(generated_nodes, 1)
        return stats

    @staticmethod
    def finalize_dfs(stats: dict, started_at: float, solution_found: bool) -> dict:
        stats["elapsed_ms"] = (perf_counter() - started_at) * 1000
        stats["solution_found"] = solution_found
        expanded_nodes = max(stats.get("expanded_nodes", 0), 1)
        generated_nodes = stats.get("generated_nodes", 0)
        pruned_by_visited = stats.get("pruned_by_visited", 0)
        stats["effective_branching_factor"] = generated_nodes / expanded_nodes
        stats["visited_prune_rate"] = pruned_by_visited / max(generated_nodes, 1)
        return stats

    @staticmethod
    def finalize_astar(stats: dict, started_at: float, solution_found: bool) -> dict:
        stats["elapsed_ms"] = (perf_counter() - started_at) * 1000
        stats["solution_found"] = solution_found
        expanded_nodes = max(stats.get("expanded_nodes", 0), 1)
        generated_nodes = stats.get("generated_nodes", 0)
        pruned_by_cost = stats.get("pruned_by_cost", 0)
        pruned_by_closed = stats.get("pruned_by_closed", 0)
        stats["effective_branching_factor"] = generated_nodes / expanded_nodes
        stats["cost_prune_rate"] = pruned_by_cost / max(generated_nodes, 1)
        stats["closed_prune_rate"] = pruned_by_closed / max(generated_nodes, 1)
        return stats

    @staticmethod
    def finalize_ucs(stats: dict, started_at: float, solution_found: bool) -> dict:
        stats["elapsed_ms"] = (perf_counter() - started_at) * 1000
        stats["solution_found"] = solution_found
        expanded_nodes = max(stats.get("expanded_nodes", 0), 1)
        generated_nodes = stats.get("generated_nodes", 0)
        dominance_pruned = stats.get("dominance_pruned", 0)
        stats["effective_branching_factor"] = generated_nodes / expanded_nodes
        stats["dominance_prune_rate"] = dominance_pruned / max(generated_nodes, 1)
        return stats

    @staticmethod
    def format_bfs(stats: Optional[dict]) -> str:
        if not stats:
            return "No BFS stats available. Run search() first."

        lines = [
            "BFS Run Stats",
            f"- solution_found: {stats.get('solution_found', False)}",
            f"- stop_reason: {stats.get('stop_reason', 'unknown')}",
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

    @staticmethod
    def format_dfs(stats: Optional[dict]) -> str:
        if not stats:
            return "No DFS stats available. Run search() first."

        lines = [
            "DFS Run Stats",
            f"- solution_found: {stats.get('solution_found', False)}",
            f"- elapsed_ms: {stats.get('elapsed_ms', 0.0):.2f}",
            f"- solution_length: {stats.get('solution_length', 0)}",
            f"- best_solution_updates: {stats.get('best_solution_updates', 0)}",
            f"- expanded_nodes: {stats.get('expanded_nodes', 0)}",
            f"- generated_nodes: {stats.get('generated_nodes', 0)}",
            f"- stale_stack_pops: {stats.get('stale_stack_pops', 0)}",
            f"- pruned_by_visited: {stats.get('pruned_by_visited', 0)}",
            f"- pruned_by_bound: {stats.get('pruned_by_bound', 0)}",
            f"- pruned_by_cycle: {stats.get('pruned_by_cycle', 0)}",
            f"- pruned_by_widening: {stats.get('pruned_by_widening', 0)}",
            f"- pruned_by_canonical: {stats.get('pruned_by_canonical', 0)}",
            f"- pruned_by_mini_batch_duplicate: {stats.get('pruned_by_mini_batch_duplicate', 0)}",
            f"- delayed_duplicate_enabled: {stats.get('delayed_duplicate_enabled', False)}",
            f"- timed_out: {stats.get('timed_out', False)}",
            f"- stop_reason: {stats.get('stop_reason', 'unknown')}",
            f"- visited_prune_rate: {stats.get('visited_prune_rate', 0.0):.2%}",
            f"- effective_branching_factor: {stats.get('effective_branching_factor', 0.0):.3f}",
            f"- peak_frontier_size: {stats.get('peak_frontier_size', 0)}",
            f"- peak_visited_size: {stats.get('peak_visited_size', 0)}",
            f"- final_frontier_size: {stats.get('final_frontier_size', 0)}",
            f"- final_visited_size: {stats.get('final_visited_size', 0)}",
        ]
        return "\n".join(lines)

    @staticmethod
    def format_astar(stats: Optional[dict]) -> str:
        if not stats:
            return "No A* stats available. Run search() first."

        solution_cost = stats.get("solution_cost")
        solution_cost_text = "n/a" if solution_cost is None else str(solution_cost)
        lines = [
            "A* Run Stats",
            f"- weight: {stats.get('weight', 0.0)}",
            f"- solution_found: {stats.get('solution_found', False)}",
            f"- stop_reason: {stats.get('stop_reason', 'unknown')}",
            f"- elapsed_ms: {stats.get('elapsed_ms', 0.0):.2f}",
            f"- solution_length: {stats.get('solution_length', 0)}",
            f"- solution_cost: {solution_cost_text}",
            f"- expanded_nodes: {stats.get('expanded_nodes', 0)}",
            f"- generated_nodes: {stats.get('generated_nodes', 0)}",
            f"- stale_heap_pops: {stats.get('stale_heap_pops', 0)}",
            f"- pruned_by_cost: {stats.get('pruned_by_cost', 0)}",
            f"- pruned_by_closed: {stats.get('pruned_by_closed', 0)}",
            f"- reopened_nodes: {stats.get('reopened_nodes', 0)}",
            f"- arena_compactions: {stats.get('arena_compactions', 0)}",
            f"- arena_nodes_reclaimed: {stats.get('arena_nodes_reclaimed', 0)}",
            f"- cost_prune_rate: {stats.get('cost_prune_rate', 0.0):.2%}",
            f"- closed_prune_rate: {stats.get('closed_prune_rate', 0.0):.2%}",
            f"- effective_branching_factor: {stats.get('effective_branching_factor', 0.0):.3f}",
            f"- peak_frontier_size: {stats.get('peak_frontier_size', 0)}",
            f"- peak_closed_size: {stats.get('peak_closed_size', 0)}",
            f"- final_frontier_size: {stats.get('final_frontier_size', 0)}",
            f"- final_closed_size: {stats.get('final_closed_size', 0)}",
            f"- move_pool_size: {stats.get('move_pool_size', 0)}",
        ]
        return "\n".join(lines)

    @staticmethod
    def format_ucs(stats: Optional[dict]) -> str:
        if not stats:
            return "No UCS stats available. Run search() first."

        solution_cost = stats.get("solution_cost")
        solution_cost_text = "n/a" if solution_cost is None else str(solution_cost)
        lines = [
            "UCS Run Stats",
            f"- solution_found: {stats.get('solution_found', False)}",
            f"- stop_reason: {stats.get('stop_reason', 'unknown')}",
            f"- elapsed_ms: {stats.get('elapsed_ms', 0.0):.2f}",
            f"- solution_length: {stats.get('solution_length', 0)}",
            f"- solution_cost: {solution_cost_text}",
            f"- expanded_nodes: {stats.get('expanded_nodes', 0)}",
            f"- generated_nodes: {stats.get('generated_nodes', 0)}",
            f"- stale_heap_pops: {stats.get('stale_heap_pops', 0)}",
            f"- dominance_pruned: {stats.get('dominance_pruned', 0)}",
            f"- dominance_prune_rate: {stats.get('dominance_prune_rate', 0.0):.2%}",
            f"- effective_branching_factor: {stats.get('effective_branching_factor', 0.0):.3f}",
            f"- peak_frontier_size: {stats.get('peak_frontier_size', 0)}",
            f"- peak_visited_size: {stats.get('peak_visited_size', 0)}",
            f"- peak_state_cache_size: {stats.get('peak_state_cache_size', 0)}",
            f"- final_frontier_size: {stats.get('final_frontier_size', 0)}",
            f"- final_visited_size: {stats.get('final_visited_size', 0)}",
            f"- move_pool_size: {stats.get('move_pool_size', 0)}",
        ]
        return "\n".join(lines)
