"""Breadth-First Search solver."""

from collections import deque

from backend.engine.engine import apply_move, get_valid_moves


class BFSAlgorithm:
    """Placeholder breadth-first solver interface."""

    def __init__(self, game_state):
        """Store initial game state for BFS search."""
        self.game_state = game_state

    def search(self):
        """Execute BFS and return a move list once implemented."""
        pass