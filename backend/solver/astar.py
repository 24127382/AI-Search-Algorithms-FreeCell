"""A* Search solver."""

from heapq import heappop, heappush

from backend.engine.engine import apply_move, get_valid_moves
from backend.solver.heuristics import zero_heuristic


class AStarAlgorithm:
    """Placeholder A* solver interface."""

    def __init__(self, game_state):
        """Store initial game state for A* search.

        Args:
            game_state: Initial board state.
        """
        self.game_state = game_state

    def search(self, heuristic_func=None):
        """Execute A* search.

        Args:
            heuristic_func: Optional heuristic callable.

        Returns:
            object: Planned move path once implementation is provided.
        """
        pass