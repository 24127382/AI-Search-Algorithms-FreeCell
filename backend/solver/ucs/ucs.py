"""Uniform Cost Search solver."""

import os
from time import perf_counter
from heapq import heappop, heappush

from backend.engine.engine import apply_move_with_forced, get_valid_moves
from backend.solver.ucs.ucs_utils import (
    decode_edge_moves,
    encode_edge_moves,
    state_id,
    ucs_move_cost,
)


UCS_RUNTIME_LOG_ENABLED = os.environ.get("UCS_RUNTIME_LOG", "1") != "0"
# UCS_RUNTIME_LOG_INTERVAL_SECONDS = float(os.environ.get("UCS_RUNTIME_LOG_INTERVAL", "10.0"))


class UCSAlgorithm:
    """Uniform-Cost Search with exact single-mode execution.

    Attributes:
        game_state: Initial search state.
        last_run_stats: Statistics from last completed run.
    """

    def __init__(self, game_state):
        """Initialize UCS with a fixed start state.

        Args:
            game_state: Initial search state.
        """
        self.game_state = game_state
        self.last_run_stats = None

    def _finalize_stats(self, stats, started_at, solution_found):
        """Finalize and persist run statistics.

        Args:
            stats: Mutable stats dictionary.
            started_at: Run start timestamp.
            solution_found: Whether run found a solution.
        """
        stats["elapsed_ms"] = (perf_counter() - started_at) * 1000
        stats["solution_found"] = solution_found
        expanded_nodes = max(stats.get("expanded_nodes", 0), 1)
        generated_nodes = stats.get("generated_nodes", 0)
        dominance_pruned = stats.get("dominance_pruned", 0)
        stats["effective_branching_factor"] = generated_nodes / expanded_nodes
        stats["dominance_prune_rate"] = dominance_pruned / max(generated_nodes, 1)
        self.last_run_stats = stats

    def format_last_run_stats(self) -> str:
        """Build a compact human-readable report for `last_run_stats`.

        Returns:
            str: Multiline summary string.
        """
        if not self.last_run_stats:
            return "No UCS stats available. Run search() first."

        stats = self.last_run_stats
        solution_cost = stats.get("solution_cost")
        solution_cost_text = "n/a" if solution_cost is None else str(solution_cost)

        lines = [
            "UCS Run Stats",
            f"- solution_found: {stats.get('solution_found', False)}",
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

    def _log_progress(self):
        """Print full runtime summary after a UCS run ends."""
        print(self.format_last_run_stats())

    @staticmethod
    def _priority_bias(state) -> int:
        """Compute tie-break bias for equal-cost nodes.

        Args:
            state: Candidate state.

        Returns:
            int: Bias where lower values are prioritized.
        """
        foundation_bits = state.foundation_bits
        foundation_total = (
            (foundation_bits & 0xF)
            + ((foundation_bits >> 4) & 0xF)
            + ((foundation_bits >> 8) & 0xF)
            + ((foundation_bits >> 12) & 0xF)
        )
        empty_tableau = sum(1 for column in state.tableau if not column)
        occupied_freecells = sum(1 for card in state.freecells if card is not None)
        progress_score = (foundation_total * 16) + (empty_tableau * 3) - occupied_freecells
        return -progress_score

    @staticmethod
    def _reconstruct_path(node_index, parent_index_arena, edge_move_ids_arena, move_pool):
        """Reconstruct full move path by walking parent links backward.

        Args:
            node_index: Terminal node index.
            parent_index_arena: Parent link arena.
            edge_move_ids_arena: Edge id arena.
            move_pool: Interned move pool.

        Returns:
            list: Ordered move path from start to goal.
        """
        path = []
        walk = node_index
        while walk >= 0:
            edge_move_ids = edge_move_ids_arena[walk]
            if not edge_move_ids:
                break
            edge_moves = decode_edge_moves(edge_move_ids, move_pool)
            path.extend(reversed(edge_moves))
            walk = parent_index_arena[walk]
        path.reverse()
        return path

    def search(self):
        """Run UCS and return an optimal path if one exists.

        Returns:
            list | None: Solution path, or `None` when no solution was found.
        """
        started_at = perf_counter()
        counter = 0
        start_state = self.game_state
        start_state_id = state_id(start_state)

        frontier = []
        heappush(frontier, (0, self._priority_bias(start_state), counter, start_state_id))

        stats = {
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
        }

        best_cost = {start_state_id: 0}
        best_node_index = {start_state_id: 0}
        parent_index_arena = [-1]
        edge_move_ids_arena = [()]

        move_pool = []
        move_index_by_signature = {}

        state_cache = {start_state_id: start_state}
    
        while frontier:
            if len(frontier) > stats["peak_frontier_size"]:
                stats["peak_frontier_size"] = len(frontier)
            if len(best_cost) > stats["peak_visited_size"]:
                stats["peak_visited_size"] = len(best_cost)
            if len(state_cache) > stats["peak_state_cache_size"]:
                stats["peak_state_cache_size"] = len(state_cache)

            cost, _, _, current_state_id = heappop(frontier)
            best_known_cost = best_cost.get(current_state_id)
            if best_known_cost is None or cost != best_known_cost:
                stats["stale_heap_pops"] += 1
                continue

            current_node_index = best_node_index.get(current_state_id)
            if current_node_index is None:
                stats["stale_heap_pops"] += 1
                continue

            current_state = state_cache.pop(current_state_id, None)
            if current_state is None:
                stats["stale_heap_pops"] += 1
                continue

            stats["expanded_nodes"] += 1

            if current_state.is_goal:
                path = self._reconstruct_path(current_node_index, parent_index_arena, edge_move_ids_arena, move_pool)
                stats["move_pool_size"] = len(move_pool)
                stats["solution_cost"] = cost
                stats["solution_length"] = len(path)
                stats["final_frontier_size"] = len(frontier)
                stats["final_visited_size"] = len(best_cost)
                self._finalize_stats(stats, started_at, solution_found=True)
                if UCS_RUNTIME_LOG_ENABLED:
                    self._log_progress()
                return path

            incoming_edge_move_ids = edge_move_ids_arena[current_node_index]
            last_move = move_pool[incoming_edge_move_ids[-1]] if incoming_edge_move_ids else None
            candidate_moves = get_valid_moves(current_state, last_move=last_move)

            for move in candidate_moves:
                next_state, forced_moves = apply_move_with_forced(current_state, move)
                edge_cost = ucs_move_cost(move, prev_state=current_state, next_state=next_state)
                if forced_moves:
                    edge_cost += sum(ucs_move_cost(applied_move) for applied_move in forced_moves)

                edge_moves = (move, *forced_moves)
                next_state_id = state_id(next_state)
                new_cost = cost + edge_cost
                stats["generated_nodes"] += 1

                old_cost = best_cost.get(next_state_id)
                if old_cost is not None and new_cost >= old_cost:
                    stats["dominance_pruned"] += 1
                    continue

                edge_move_ids = encode_edge_moves(edge_moves, move_index_by_signature, move_pool)
                node_index = len(parent_index_arena)
                best_cost[next_state_id] = new_cost
                best_node_index[next_state_id] = node_index
                parent_index_arena.append(current_node_index)
                edge_move_ids_arena.append(edge_move_ids)
                state_cache[next_state_id] = next_state
                counter += 1
                heappush(frontier, (new_cost, self._priority_bias(next_state), counter, next_state_id))

        stats["move_pool_size"] = len(move_pool)
        stats["final_frontier_size"] = len(frontier)
        stats["final_visited_size"] = len(best_cost)
        self._finalize_stats(stats, started_at, solution_found=False)
        if UCS_RUNTIME_LOG_ENABLED:
            self._log_progress()
        return None
