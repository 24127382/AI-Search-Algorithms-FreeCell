"""A* Search solver."""

from heapq import heappop, heappush

from backend.engine.engine import apply_move, get_valid_moves
from backend.solver.heuristics import zero_heuristic
from backend.solver.ucs_utils import state_id, ucs_move_cost


class AStarAlgorithm:
    def __init__(self, game_state):
        self.game_state = game_state

    def search(self, heuristic_func=None):
        pass