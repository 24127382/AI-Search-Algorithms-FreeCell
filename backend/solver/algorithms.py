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

# import heapq
# from backend.engine.engine import get_valid_moves, apply_move

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

        """
        if algorithm == 'BFS':
            return self._bfs()
        elif algorithm == 'DFS':
            return self._dfs()
        elif algorithm == 'UCS':
            return self._ucs()
        elif algorithm == 'A*':
            if heuristic_func is None:
                raise ValueError("A* requires a heuristic_func argument.")
            return self._a_star(heuristic_func)
        else:
            raise ValueError("Unknown algorithm: {}".format(algorithm))

    def _bfs(self):
        pass

    def _dfs(self):
        pass

    def _ucs(self):
        pass

    def _a_star(self, heuristic_func):
        """
        """
        A* search using the provided admissible heuristic.

        Each node in the frontier is: (f, g, state, path)
          - f = g + h  (priority)
          - g = cost so far (number of moves)
          - path = list of Move objects leading here
        """
        start = self.game_state

        # (f_score, g_score, state, path)
        frontier = []
        g_start = 0
        h_start = heuristic_func(start)
        heapq.heappush(frontier, (g_start + h_start, g_start, start, []))

        # visited maps state -> best g seen so far
        visited = {}

        while frontier:
            f, g, state, path = heapq.heappop(frontier)

            # Skip if we already found a cheaper route to this state
            if state in visited and visited[state] <= g:
                continue
            visited[state] = g

            if is_goal(state):
                return path  # List of Move objects = solution

            for move in get_valid_moves(state):
                next_state = apply_move(state, move)
                next_g = g + 1  # Each move costs 1
                next_h = heuristic_func(next_state)
                next_f = next_g + next_h

                if next_state not in visited or visited[next_state] > next_g:
                    heapq.heappush(
                        frontier,
                        (next_f, next_g, next_state, path + [move])
                    )

        return None  # No solution found

