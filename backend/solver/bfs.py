"""Breadth-First Search solver."""

from collections import deque

from backend.engine.engine import apply_move, get_valid_moves


class BFSAlgorithm:
    """Placeholder breadth-first solver interface."""

    def __init__(self, game_state):
        """Store initial game state for BFS search.

        Args:
            game_state: Initial board state.
        """
        self.game_state = game_state

    def search(self):
        """Execute BFS search.

        Returns:
            object: Planned move path once implementation is provided.
        """
        queue = deque([(self.game_state, [])])
        visited = set()
        
        while queue:
            state, path = queue.popleft()
            if state in visited:
                continue
            visited.add(state)
            
            if state.is_goal:
                return path
            
            valid_moves = get_valid_moves(state)
            for move in valid_moves:
                new_state = apply_move(state, move)
                if new_state not in visited:
                    queue.append((new_state, path + [move]))
                    
        return None