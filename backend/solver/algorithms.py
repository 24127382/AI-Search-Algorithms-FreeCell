'''
algorithms.py

This module implements search algorithms for freecell.

Algorithms included:
- BFS
- DFS
- UCS
- A*
'''
import heapq
from engine.engine import get_valid_moves, apply_move, is_goal

class SearchAlgorithm:
    def __init__(self, game_state):
        self.game_state = game_state

    def search(self, algorithm, heuristic_func=None):
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
