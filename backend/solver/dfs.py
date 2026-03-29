import time
from backend.engine.engine import apply_move, get_valid_moves

class DFSAlgorithm:
    """Depth-First Search solver with performance metrics."""

    def __init__(self, game_state):
        """Store initial game state for DFS search.

        Args:
            game_state: Initial board state.
        """
        self.game_state = game_state
        # Kh?i t?o c�c bi?n luu tr? th�ng s?
        self.expanded_nodes = 0
        self.peak_stack_size = 0
        self.execution_time_ms = 0.0

    def search(self):
        """Execute DFS search and track performance metrics.

        Returns:
            list: Path of moves from initial state to goal state, or None if no solution found.
        """
        # B?t d?u do th?i gian
        start_time = time.perf_counter()

        # Stack stores tuples of (state, path_to_state)
        stack = [(self.game_state, [])]
        visited = set()

        self.expanded_nodes = 0
        self.peak_stack_size = 0

        while stack:
            # Ghi nh?n k�ch thu?c Stack l?n nh?t (Peak Stack Size)
            if len(stack) > self.peak_stack_size:
                self.peak_stack_size = len(stack)

            state, path = stack.pop()
            state_hash = hash(state)

            if state_hash in visited:
                continue
            
            # ��nh d?u d� tham v� tang bi?n d?m s? node d� khai tri?n
            visited.add(state_hash)
            self.expanded_nodes += 1

            if state.is_goal:
                self.execution_time_ms = (time.perf_counter() - start_time) * 1000
                self._print_stats(path, visited)
                return path

            valid_moves = get_valid_moves(state)

            for move in valid_moves:
                new_state = apply_move(state, move)

                if new_state.is_goal:
                    final_path = path + [move]
                    self.execution_time_ms = (time.perf_counter() - start_time) * 1000
                    # C?p nh?t peak_stack_size m?t l?n cu?i n?u c?n
                    self.peak_stack_size = max(self.peak_stack_size, len(stack) + 1)
                    self._print_stats(final_path, visited)
                    return final_path

                if hash(new_state) not in visited:
                    stack.append((new_state, path + [move]))

        # Tru?ng h?p kh�ng t�m th?y du?ng di (Unsolvable)
        self.execution_time_ms = (time.perf_counter() - start_time) * 1000
        self._print_stats(None, visited)
        return None

    def _print_stats(self, path, visited):
        """Print DFS search statistics."""
        total_steps = len(path) if path else 0
        nodes_visited = len(visited)
        print(f"\n--- DFS Search Results ---")
        print(f"Time (ms): {self.execution_time_ms:.2f}")
        print(f"Total Steps: {total_steps}")
        print(f"Expanded Nodes: {self.expanded_nodes}")
        print(f"Peak Frontier: {self.peak_stack_size}")
        print(f"Nodes Visited: {nodes_visited}")
        print(f"----------------------------\n")
