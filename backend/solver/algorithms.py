"""Backward-compatible SearchAlgorithm facade."""

from backend.model.state import State
from backend.solver.astar import AStarAlgorithm
from backend.solver.bfs import BFSAlgorithm
from backend.solver.dfs import DFSAlgorithm
from backend.solver.ucs.ucs import UCSAlgorithm
from enum import Enum

class AlgorithmMode(Enum):
    """High-level UCS policy presets exposed to the UI layer."""
    FIRST = "first"
    SPEED = "speed"
    MEMORY = "memory"

class SearchAlgorithm:
    """Small facade that dispatches to concrete search implementations."""

    def __init__(self, game_state, mode=AlgorithmMode.SPEED.value):
        """Bind algorithm handlers for a fixed initial game state.

        Args:
            game_state: Initial board state for solver execution.
            mode: UCS mode preset used when algorithm is UCS.
        """
        self.game_state = game_state
        self._handlers = {
            "BFS": BFSAlgorithm(self.game_state).search,
            "DFS": DFSAlgorithm(self.game_state).search,
            "UCS": UCSAlgorithm(self.game_state, mode).search,
            "A*": AStarAlgorithm(self.game_state).search,
        }
        
    def search(self, algorithm, heuristic_func=None):
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
