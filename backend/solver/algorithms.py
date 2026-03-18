"""Backward-compatible SearchAlgorithm facade."""

from backend.model.state import State
from backend.solver.astar import AStarAlgorithm
from backend.solver.bfs import BFSAlgorithm
from backend.solver.dfs import DFSAlgorithm
from backend.solver.ucs.ucs import UCSAlgorithm
from enum import Enum

class AlgorithmMode(Enum):
    FIRST = "first"
    SPEED = "speed"
    MEMORY = "memory"

class SearchAlgorithm:
    def __init__(self, game_state, mode=AlgorithmMode.SPEED.value):
        self.game_state = game_state
        self._handlers = {
            "BFS": BFSAlgorithm(self.game_state).search,
            "DFS": DFSAlgorithm(self.game_state).search,
            "UCS": UCSAlgorithm(self.game_state, mode).search,
            "A*": AStarAlgorithm(self.game_state).search,
        }
        
    def search(self, algorithm, heuristic_func=None):
        handler = self._handlers.get(algorithm)
        if handler is None:
            raise ValueError(f"Unknown algorithm: {algorithm}")
        if algorithm == "A*":
            return handler(heuristic_func)
        return handler()
