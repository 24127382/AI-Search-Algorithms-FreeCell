"""Depth-First Search solver with incremental Zobrist hashing.

Uses Zobrist hashing for visited state detection, providing O(1) hash lookups
and compact 64-bit hash values instead of storing full state objects.
"""

from backend.engine.engine import apply_move, get_valid_moves
from backend.solver.utils import get_zobrist_table, ZobristHash


class DFSAlgorithm:
    """Depth-First Search with incremental Zobrist hashing.
    
    Maintains a zobrist hash for each state visited, enabling efficient
    transposition detection and state deduplication.
    """

    def __init__(self, game_state):
        """Initialize DFS solver.

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
        """Execute DFS search using Zobrist hashing for visited tracking.

        Uses a stack for LIFO exploration and zobrist hashes for cycle
        detection. Hash-based deduplication is more memory-efficient than
        storing full state objects.

        Returns:
            list: Path of moves from initial to goal state, or None if unsolvable.
        """
        # Stack contains (state, path_list)
        stack = [(self.game_state, [])]
        visited = set()

        while stack:
            state, path = stack.pop()
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
                    stack.append((new_state, path + [move]))

        return None