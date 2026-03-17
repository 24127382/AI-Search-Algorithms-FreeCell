"""Breadth-First Search solver."""

from collections import deque

from backend.engine.engine import apply_move, get_valid_moves


class BFSAlgorithm:
    def __init__(self, game_state):
        self.game_state = game_state

    def search(self):
        pass