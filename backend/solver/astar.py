"""A* Search solver."""

from heapq import heappop, heappush

from backend.engine.engine import apply_move, get_valid_moves
from backend.solver.heuristics import zero_heuristic


class AStarAlgorithm:
    """Placeholder A* solver interface."""

    def __init__(self, game_state):
        """Store initial game state for A* search."""
        self.game_state = game_state

    def search(self, heuristic_func=None):
        """Execute A* and return a move list once implemented."""
        pass