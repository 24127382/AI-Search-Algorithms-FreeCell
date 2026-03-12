'''
algorithms.py

This module implements search algorithms for freecell.

Algorithms included:
- BFS
- DFS
- UCS
- A*
'''

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
        pass
    
    def _dfs(self):
        pass
    
    def _ucs(self):
        pass
    
    def _a_star(self):
        pass
        
