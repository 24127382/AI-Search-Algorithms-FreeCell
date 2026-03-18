"""Depth-First Search solver."""

from backend.engine.engine import apply_move, get_valid_moves


class DFSAlgorithm:
    """Placeholder depth-first solver interface."""

    def __init__(self, game_state):
        """Store initial game state for DFS search.

        Args:
            game_state: Initial board state.
        """
        self.game_state = game_state

    def search(self):
        """Execute DFS search.

        Returns:
            object: Planned move path once implementation is provided.
        """
        pass