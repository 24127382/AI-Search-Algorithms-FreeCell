"""Depth-First Search solver."""

from backend.engine.engine import apply_move, get_valid_moves
from backend.solver.ucs_utils import state_id


class DFSAlgorithm:
    def __init__(self, game_state):
        self.game_state = game_state

    def search(self):
        pass