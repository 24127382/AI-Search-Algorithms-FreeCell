"""Depth-First Search solver with parent pointers and cycle detection.

THEORETICAL GUARANTEES:
- Completeness: YES, ONLY because we maintain a global visited set.
  Without visited set, DFS could loop infinitely (e.g., card F->T->F->T...).
- Optimality: NO. DFS finds *a* solution, not necessarily the shortest.

IMPORTANT DISTINCTION FROM "TREE-SEARCH" DFS:
- This is GRAPH-SEARCH DFS (with global visited set).
- Tree-search DFS has O(1) space but risks infinite loops and revisits.
- Graph-search DFS has O(b*d) space (stack) but requires visited set O(# unique states).

MEMORY MODEL CLARIFICATION:
- Peak memory = stack size (O(b*d)) + visited set O(# unique states)
- The visited set keeps growing throughout search, unlike stack which shrinks on backtrack.
- For hard deals: stack might peak at 1000s of states, visited set might reach 10^6+ states.
- This is fundamentally different from path-space complexity O(d) mentioned in some references.

SOLUTION QUALITY:
- Solution length highly dependent on move ordering.
- Expected to be 2-10x longer than BFS optimal paths.
"""

import time
from typing import List, Optional, Tuple

from backend.engine.engine import apply_move, get_valid_moves
from backend.model.state import State
from backend.model.move import Move
from backend.search.instrumentation import MetricsCollector, SearchMetrics


class DFSAlgorithm:
    """Depth-First Search with parent-pointer path reconstruction and global visited set.
    
    Completeness: Guaranteed by global visited set (prevents infinite loops).
    Solution quality: Arbitrary (depends on move ordering in get_valid_moves).
    """

    def __init__(self, initial_state: State, collect_metrics: bool = True, max_nodes: int = 500000):
        """Initialize DFS algorithm.
        
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
        """Execute DFS search and return move sequence.
        
        Returns:
            List[Move]: Sequence of moves from initial state to goal, or None if unsolvable.
            
        As per DFS theory:
        - Will find a solution if one exists (completeness via visited set)
        - Solution is NOT guaranteed to be shortest (non-optimal)
        
        Stack-based iterative implementation (not recursive) to avoid Python stack limits.
        """
        collector = MetricsCollector() if self.collect_metrics else None
        start_time = time.time()
        
        if collector:
            collector.__enter__()
        
        try:
            # Parent pointers: maps state_hash -> (parent_hash, move_to_reach_here)
            parents: dict[int, Tuple[Optional[int], Optional[Move]]] = {}
            
            # Zobrist hash -> State for collision safety
            state_hashes: dict[int, State] = {}
            
            # Global visited set: marks all states ever pushed onto stack
            # This is CRITICAL for completeness and avoids infinite loops.
            visited_hashes = set()
            
            stack = [self.initial_state]
            
            initial_hash = hash(self.initial_state)
            visited_hashes.add(initial_hash)
            state_hashes[initial_hash] = self.initial_state
            parents[initial_hash] = (None, None)  # Initial state has no parent
            
            expanded_count = 0
            
            while stack and expanded_count < self.max_nodes:
                if collector:
                    collector.record_expansion(len(stack))
                
                current_state = stack.pop()
                current_hash = hash(current_state)
                expanded_count += 1
                
                # Check goal
                if current_state.is_goal:
                    path = self._reconstruct_path(current_hash, parents, state_hashes)
                    elapsed = time.time() - start_time
                    
                    if collector:
                        collector.__exit__(None, None, None)
                        self.metrics = collector.get_metrics(
                            algorithm="DFS",
                            time_seconds=elapsed,
                            solution_length=len(path)
                        )
                    
                    return path
                
                # Expand successors
                # Push in reverse order so first valid move is explored first (LIFO)
                valid_moves = get_valid_moves(current_state)
                for move in reversed(valid_moves):
                    next_state = apply_move(current_state, move)
                    next_hash = hash(next_state)
                    
                    if next_hash not in visited_hashes:
                        visited_hashes.add(next_hash)
                        state_hashes[next_hash] = next_state
                        parents[next_hash] = (current_hash, move)
                        stack.append(next_state)
            
            # No solution found
            elapsed = time.time() - start_time
            if collector:
                collector.__exit__(None, None, None)
                self.metrics = collector.get_metrics(
                    algorithm="DFS",
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
        parents: dict[int, Tuple[Optional[int], Optional[Move]]],
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
