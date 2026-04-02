"""Breadth-First Search solver with incremental Zobrist hashing.

Uses Zobrist hashing for visited state detection, providing O(1) hash lookups
and compact 64-bit hash values instead of storing full state objects.
"""

from collections import deque
from backend.engine.engine import apply_move, get_valid_moves
from backend.solver.utils import get_zobrist_table, ZobristHash


class BFSAlgorithm:
    """Breadth-First Search with incremental Zobrist hashing.
    
    Finds the shortest path using BFS exploration order while using
    zobrist hashes for memory-efficient visited state tracking.
    """

    def __init__(self, game_state):
        """Initialize BFS solver.

        Args:
            game_state: Initial board state.
        """
        self.game_state = game_state
        self.zobrist_table = get_zobrist_table()

    def _compute_state_hash(self, state) -> int:
        """Compute zobrist hash for a state.
        
        Uses the shared zobrist table for consistent hashing across calls.
        
        Args:
            state: FreeCell game state.
        
        Returns:
            int: 64-bit zobrist hash.
        """
        hasher = ZobristHash(self.zobrist_table)
        return hasher.hash_state(state)

    def search(self):
        """Execute BFS search using Zobrist hashing.
        
        Finds shortest solution path by exploring states level-by-level.
        Uses zobrist hashes (64-bit integers) instead of storing full
        state objects, reducing memory consumption significantly.

        Returns:
            list: Shortest path of moves from initial to goal state, or None if unsolvable.
        """
        queue = deque([(self.game_state, [])])
        visited = set()
        
        while queue:
            state, path = queue.popleft()
            state_hash = self._compute_state_hash(state)
            
            if state_hash in visited:
                continue
            visited.add(state_hash)
            
            if state.is_goal:
                return path
            
            valid_moves = get_valid_moves(state)
            for move in valid_moves:
                new_state = apply_move(state, move)
                new_state_hash = self._compute_state_hash(new_state)
                if new_state_hash not in visited:
                    queue.append((new_state, path + [move]))
                    
        return None