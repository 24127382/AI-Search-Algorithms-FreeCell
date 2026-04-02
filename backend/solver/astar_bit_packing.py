"""A* solver with bit-packing hash (baseline control group).

This is the standard approach using the existing State.board_code for hashing.
Hash computation is O(n) in the board complexity.

Used as the baseline control for benchmarking against Zobrist hashing.
"""

from heapq import heappop, heappush
from time import perf_counter
from typing import Callable, Optional, List, Tuple
import os

from backend.engine.engine import apply_move_with_forced, get_valid_moves
from backend.solver.heuristics import combined_heuristic
from backend.solver.ucs.ucs_utils import ucs_move_cost

ASTAR_BIT_PACKING_LOG = os.environ.get("ASTAR_BIT_PACKING_LOG", "1") != "0"


class AStarBitPackingHash:
    """A* with bit-packing state hashing (baseline).
    
    Uses State.board_code as the hash key. This represents the current
    production approach where the board is serialized into a compact
    bit field.
    
    Attributes:
        start_state: Initial board state.
        heuristic_func: h(state) -> int heuristic.
        weight: Weighted A* inflation factor.
        should_cancel: Cancellation callback.
        last_run_stats: Statistics from last search.
    """

    def __init__(
        self,
        start_state,
        heuristic_func: Callable = None,
        weight: float = 5.0,
        should_cancel: Optional[Callable] = None,
    ):
        self.start_state = start_state
        self.heuristic_func = heuristic_func or combined_heuristic
        self.weight = weight
        self.should_cancel = should_cancel or (lambda: False)
        self.last_run_stats = {}

    def search(self) -> Tuple[Optional[List], dict]:
        """Run weighted A* search using bit-packing hashes.
        
        Returns:
            (solution_path, stats) where solution_path is a list of moves
            (or None if no solution found), and stats is a dict with
            timing and node count metrics.
        """
        start_time = perf_counter()
        stats = {
            "nodes_expanded": 0,
            "nodes_generated": 0,
            "frontier_max_size": 0,
            "hash_computations": 0,
            "hash_total_time_ms": 0.0,
            "search_depth": 0,
            "nodes_at_depth": {},  # Track nodes expanded at each depth
        }

        # Use board_code as hash key
        start_h = self.heuristic_func(self.start_state)
        start_f = start_h  # g(start) = 0
        initial_entry = (start_f, 0, 0, self.start_state)  # (f, counter, depth, state)
        
        frontier = [initial_entry]
        closed_set = set()
        counter = 1
        
        while frontier and not self.should_cancel():
            if len(frontier) > stats["frontier_max_size"]:
                stats["frontier_max_size"] = len(frontier)

            f_val, _, depth, current = heappop(frontier)
            
            # Compute hash (this is the bit packing cost we're measuring)
            hash_start = perf_counter()
            state_hash = hash(current.board_code)
            hash_duration = (perf_counter() - hash_start) * 1000
            stats["hash_computations"] += 1
            stats["hash_total_time_ms"] += hash_duration
            
            if state_hash in closed_set:
                continue
            
            closed_set.add(state_hash)
            stats["nodes_expanded"] += 1
            stats["search_depth"] = max(stats["search_depth"], depth)
            stats["nodes_at_depth"][depth] = stats["nodes_at_depth"].get(depth, 0) + 1
            
            # Check goal
            if current.is_goal:
                elapsed = (perf_counter() - start_time) * 1000
                stats["elapsed_ms"] = elapsed
                stats["solution_found"] = True
                stats["solution_depth"] = depth
                self.last_run_stats = stats
                return ([], stats)  # Empty list for simplicity; path reconstruction omitted
            
            # Expand neighbors
            moves = get_valid_moves(current)
            for move in moves:
                next_state, forced_moves = apply_move_with_forced(current, move)
                next_hash = hash(next_state.board_code)
                
                if next_hash not in closed_set:
                    g_next = depth + ucs_move_cost(move)
                    h_next = self.heuristic_func(next_state)
                    f_next = g_next + self.weight * h_next
                    
                    stats["nodes_generated"] += 1
                    heappush(frontier, (f_next, counter, depth + 1, next_state))
                    counter += 1
        
        elapsed = (perf_counter() - start_time) * 1000
        stats["elapsed_ms"] = elapsed
        stats["solution_found"] = False
        self.last_run_stats = stats
        return (None, stats)
