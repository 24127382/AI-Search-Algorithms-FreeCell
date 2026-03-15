'''
algorithms.py

This module implements search algorithms for freecell.

Algorithms included:
- BFS
- DFS
- UCS
- A*
'''
from heapq import heappush, heappop
from backend.engine.engine import get_valid_moves, apply_move, is_goal

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
        counter = 0
        frontier = []
        heappush(frontier, (0, counter, self.game_state, []))
        
        # Set to track visited states to avoid cycles
        # Note: state needs to have a __hash__ and __eq__ method implemented
        explored = set()
        
        while frontier:
            cost, _, current_state, path = heappop(frontier)
            
            if is_goal(current_state):
                return path
            
            if current_state in explored:
                continue
            
            explored.add(current_state)
            
            # Generate neighbors
            for move in get_valid_moves(current_state):
                next_state = apply_move(current_state, move)
                if next_state not in explored:
                    counter += 1
                    
                    # Calculate optimal move cost based on strategic value in FreeCell:
                    # 1. To Foundation (cost = 1): Directly achieves the game's goal. Cheapest cost to prioritize completion.
                    # 2. Freecell to Tableau (cost = 2): Frees up a valuable freecell space, increasing future mobility.
                    # 3. Tableau to Tableau (cost = 3): Neutral organizing move. More expensive than freeing a cell.
                    # 4. To Freecell (cost = 4): Consumes a limited freecell, reducing mobility. Most expensive.
                    if move.to_pos[0] == 'foundation':
                        move_cost = 1
                    elif move.from_pos[0] == 'freecell' and move.to_pos[0] == 'tableau':
                        move_cost = 2
                    elif move.from_pos[0] == 'tableau' and move.to_pos[0] == 'tableau':
                        move_cost = 3
                    elif move.to_pos[0] == 'freecell':
                        move_cost = 4
                    else:
                        move_cost = 3 # Fallback
                        
                    heappush(frontier, (cost + move_cost, counter, next_state, path + [move]))
                    
        return None  # No solution found
    
    def _a_star(self):
        pass