"""Backward-compatible SearchAlgorithm facade."""

from typing import Callable

from backend.solver.astar import AStarAlgorithm
from backend.solver.bfs import BFSAlgorithm
from backend.solver.dfs import DFSAlgorithm
from backend.solver.ucs import UCSAlgorithm
from backend.solver.utils.heuristics import (
    buried_cards,
    combined_heuristic,
    foundation_distance,
    zero_heuristic,
)

SUPPORTED_SOLVER_ALGORITHMS = ("BFS", "DFS", "UCS", "A*")


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
        self._factories: dict[str, Callable[[], object]] = {
            "BFS": lambda: BFSAlgorithm(
                self.game_state, should_cancel=self.should_cancel
            ),
            "DFS": lambda: DFSAlgorithm(
                self.game_state, should_cancel=self.should_cancel
            ),
            "UCS": lambda: UCSAlgorithm(
                self.game_state, should_cancel=self.should_cancel
            ),
            "A*": lambda: AStarAlgorithm(
                self.game_state, should_cancel=self.should_cancel
            ),
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
        if algorithm not in SUPPORTED_SOLVER_ALGORITHMS:
            raise ValueError(f"Unknown algorithm: {algorithm}")

        solver = self._factories[algorithm]()
        if algorithm == "A*":
            return solver.search(heuristic_func)
        return solver.search()
