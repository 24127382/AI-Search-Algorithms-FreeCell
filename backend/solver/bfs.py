"""Breadth-First Search solver with Zobrist hashing for memory efficiency."""

from collections import deque

from backend.engine.engine import apply_move, get_valid_moves


class BFSAlgorithm:
    """Breadth-first solver using Zobrist hashing for visited state tracking."""

    def __init__(self, game_state):
        """Store initial game state for BFS search.

        Args:
            game_state: Initial board state.
        """
        self.game_state = game_state

    def search(self):
        """Execute BFS search using Zobrist hashing for memory efficiency.
        
        Uses Zobrist hashing (64-bit integers) instead of storing full state
        objects in visited set, significantly reducing memory consumption.

        Returns:
            object: Planned move path once implementation is provided.
        """
        queue = deque([(self.game_state, [])])
        visited = set()
        
        while queue:
            state, path = queue.popleft()
            state_hash = hash(state)  # Zobrist hash from State.__hash__()
            
            if state_hash in visited:
                continue
            visited.add(state_hash)
            
            if state.is_goal:
                return path
            
            valid_moves = get_valid_moves(state)
            for move in valid_moves:
                new_state = apply_move(state, move)
                new_state_hash = hash(new_state)
                if new_state_hash not in visited:
                    queue.append((new_state, path + [move]))
                    
        return None