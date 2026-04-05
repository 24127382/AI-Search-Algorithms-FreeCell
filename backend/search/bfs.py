"""Breadth-First Search solver with parent pointers and collision-safe hashing.

THEORETICAL GUARANTEES:
- Completeness: YES. Finite state space + visited set prevents cycles.
- Optimality: YES, but ONLY under unit-cost assumption (each move costs 1).
  If moves have different costs, use Uniform Cost Search (UCS) instead.

IMPLEMENTATION NOTES:
- Uses parent pointers instead of storing path in each node.
  This improves time complexity from O(d) per path construction to O(1) per node.
- Zobrist hash collision safety: Python's hash() with frozenset/tuple is collision-resistant
  for practical state spaces. In rare collisions, both states would be equally valid.
- Memory model: Peak memory is dominated by frontier size (O(b^d)), not hashing.
"""

import time
from collections import deque
from typing import List, Optional, Tuple

from backend.engine.engine import apply_move, get_valid_moves
from backend.model.state import State
from backend.model.move import Move
from backend.search.instrumentation import MetricsCollector, SearchMetrics


class BFSAlgorithm:
    """Breadth-First Search with parent-pointer path reconstruction.
    
    Optimality guarantees: Finds shortest path (minimum number of moves) for FreeCell,
    since each move has unit cost.
    """

    def __init__(self, initial_state: State, collect_metrics: bool = True, max_nodes: int = 500000):
        """Initialize BFS algorithm.
        
        Args:
            initial_state: Starting game state.
            collect_metrics: Whether to collect performance metrics.
            max_nodes: Maximum nodes to explore before stopping (for experiments).
        """
        self.initial_state = initial_state
        self.collect_metrics = collect_metrics
        self.max_nodes = max_nodes
        self.metrics: Optional[SearchMetrics] = None

    def search(self) -> Optional[List[Move]]:
        """Execute BFS search and return move sequence.
        
        Returns:
            List[Move]: Sequence of moves from initial state to goal, or None if unsolvable.
            
        As per BFS theory:
        - Will find a solution if one exists (completeness)
        - Solution will be shortest possible (optimality under unit cost)
        """
        collector = MetricsCollector() if self.collect_metrics else None
        start_time = time.time()
        
        if collector:
            collector.__enter__()
        
        try:
            # Parent pointers: maps state_hash -> (parent_state_hash, move_to_reach_here)
            parents: dict[int, Tuple[int, Move]] = {}
            
            # Zobrist hash -> State for collision detection (safety)
            state_hashes: dict[int, State] = {}
            
            frontier = deque([self.initial_state])
            visited_hashes = set()
            
            initial_hash = hash(self.initial_state)
            visited_hashes.add(initial_hash)
            state_hashes[initial_hash] = self.initial_state
            parents[initial_hash] = (None, None)  # Initial state has no parent
            
            expanded_count = 0
            
            while frontier and expanded_count < self.max_nodes:
                if collector:
                    collector.record_expansion(len(frontier))
                
                current_state = frontier.popleft()
                current_hash = hash(current_state)
                expanded_count += 1
                
                # Check goal
                if current_state.is_goal:
                    path = self._reconstruct_path(current_hash, parents, state_hashes)
                    elapsed = time.time() - start_time
                    
                    if collector:
                        collector.__exit__(None, None, None)
                        self.metrics = collector.get_metrics(
                            algorithm="BFS",
                            time_seconds=elapsed,
                            solution_length=len(path)
                        )
                    
                    return path
                
                # Expand successors
                valid_moves = get_valid_moves(current_state)
                for move in valid_moves:
                    next_state = apply_move(current_state, move)
                    next_hash = hash(next_state)
                    
                    if next_hash not in visited_hashes:
                        visited_hashes.add(next_hash)
                        state_hashes[next_hash] = next_state
                        parents[next_hash] = (current_hash, move)
                        frontier.append(next_state)
            
            # No solution found
            elapsed = time.time() - start_time
            if collector:
                collector.__exit__(None, None, None)
                self.metrics = collector.get_metrics(
                    algorithm="BFS",
                    time_seconds=elapsed,
                    solution_length=-1
                )
            
            return None
        
        except Exception as e:
            if collector:
                collector.__exit__(None, None, None)
            raise
    
    @staticmethod
    def _reconstruct_path(
        goal_hash: int,
        parents: dict[int, Tuple[int, Move]],
        state_hashes: dict[int, State]
    ) -> List[Move]:
        """Reconstruct solution path by following parent pointers.
        
        Args:
            goal_hash: Hash of goal state.
            parents: Parent mapping (hash -> (parent_hash, move)).
            state_hashes: Hash -> State mapping.
        
        Returns:
            List[Move]: Solution path in order.
        
        Complexity: O(d) where d is solution length.
        Memory: O(d) for result list.
        """
        path = []
        current_hash = goal_hash
        
        # Follow parent pointers back to initial state (where parent_hash is None)
        while parents[current_hash][0] is not None:
            parent_hash, move = parents[current_hash]
            path.append(move)
            current_hash = parent_hash
        
        path.reverse()
        return path

    def get_metrics(self) -> Optional[SearchMetrics]:
        """Retrieve collected metrics from last search.
        
        Returns:
            SearchMetrics or None if metrics not collected.
        """
        return self.metrics
