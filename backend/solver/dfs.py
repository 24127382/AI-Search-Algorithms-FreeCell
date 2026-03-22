"""Depth-First Search solver."""

from backend.engine.engine import apply_move, get_valid_moves


class DFSAlgorithm:
    """Depth-First Search solver."""

    def __init__(self, game_state):
        """Store initial game state for DFS search.

        Args:
            game_state: Initial board state.
        """
        self.game_state = game_state

    def search(self):
        """Execute DFS search.

        Uses a stack for Last-In-First-Out (LIFO) exploration and a visited set
        to avoid cycles.

        Returns:
            list: Planned move path from initial state to goal state, or None if no solution.
        """
        # Stack stores tuples of (state, path_to_state)
        stack = [(self.game_state, [])]
        visited = set()

        while stack:
            state, path = stack.pop()
            state_hash = hash(state)

            if state_hash in visited:
                continue
            visited.add(state_hash)

            if state.is_goal:
                return path

            valid_moves = get_valid_moves(state)

            for move in valid_moves:
                new_state = apply_move(state, move)

                if new_state.is_goal:
                    return path + [move]

                if hash(new_state) not in visited:
                    stack.append((new_state, path + [move]))

        return None