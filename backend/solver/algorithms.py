'''
algorithms.py

This module implements search algorithms for freecell.

Algorithms included:
- BFS
- DFS
- UCS
- A*
'''

from collections import deque

from backend.engine.engine import apply_move, get_valid_moves, is_goal


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
            return self._a_star(heuristic_func)
        else:
            raise ValueError("Unknown algorithm: {}".format(algorithm))
        
    def _bfs(self):
        queue = deque([(self.game_state, [])])
        visited = {self.game_state}
        
        while queue:
            state, path = queue.popleft()
            if is_goal(state):
                return path
            
            for move in get_valid_moves(state):
                new_state = apply_move(state, move)
                if new_state not in visited:
                    visited.add(new_state)
                    queue.append((new_state, path + [move]))

        return None  # No solution found
    
    def _dfs(self):
        pass
    
    def _ucs(self):
        pass
    
    def _a_star(self):
        pass
        
