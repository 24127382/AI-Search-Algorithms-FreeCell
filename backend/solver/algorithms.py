"""Backward-compatible SearchAlgorithm facade."""

from backend.solver.astar import AStarAlgorithm
from backend.solver.bfs import BFSAlgorithm
from backend.solver.dfs import DFSAlgorithm
from backend.solver.heuristics import combined_heuristic, foundation_distance, buried_cards, zero_heuristic
from backend.solver.ucs.ucs import UCSAlgorithm

class SearchAlgorithm:
    """Small facade that dispatches to concrete search implementations."""

    def __init__(self, game_state, should_cancel=None):
        """Bind algorithm handlers for a fixed initial game state.

        Args:
            game_state: Initial board state for solver execution.
            should_cancel: Optional callable returning True when solve should stop.
        """
        self.game_state = game_state
        self.should_cancel = should_cancel or (lambda: False)
        self._handlers = {
            "BFS": BFSAlgorithm(self.game_state).search,
            "DFS": DFSAlgorithm(self.game_state).search,
            "UCS": UCSAlgorithm(self.game_state, should_cancel=self.should_cancel).search,
            "A*": AStarAlgorithm(self.game_state,weight=5.0, should_cancel=self.should_cancel).search,
        }

    def search(self, algorithm, heuristic_func=combined_heuristic):
        """Run the selected solver and return computed path.

        Args:
            algorithm: Solver key (e.g. "BFS", "DFS", "UCS", "A*").
            heuristic_func: Optional heuristic used only by A*.

        Returns:
            object: Solver-specific path result.

        Raises:
            ValueError: If `algorithm` key is unsupported.
        """
        handler = self._handlers.get(algorithm)
        if handler is None:
            raise ValueError(f"Unknown algorithm: {algorithm}")
        if algorithm == "A*":
            return handler(heuristic_func)
        return handler()
