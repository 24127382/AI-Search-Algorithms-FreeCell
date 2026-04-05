"""Backward-compatible SearchAlgorithm facade."""

from backend.solver.astar import AStarAlgorithm
from backend.solver.bfs import BFSAlgorithm
from backend.solver.dfs import DFSAlgorithm
from backend.solver.heuristics import combined_heuristic, foundation_distance, buried_cards, zero_heuristic
from backend.solver.ucs.ucs import UCSAlgorithm

class SearchAlgorithm:
    """Small facade that dispatches to concrete search implementations."""

    def __init__(self, game_state, should_cancel=None):
        """Bind algorithm handlers for a fixed initial game state.

        Args:
            game_state: Initial board state for solver execution.
            should_cancel: Optional callable returning True when solve should stop.
        """
        self.game_state = game_state
        self.should_cancel = should_cancel or (lambda: False)
        
        # Store algorithm instances for access to their methods (e.g., get_user_feedback)
        self.bfs_instance = BFSAlgorithm(self.game_state, should_cancel=self.should_cancel)
        self.dfs_instance = DFSAlgorithm(self.game_state, should_cancel=self.should_cancel)
        self.ucs_instance = UCSAlgorithm(self.game_state, should_cancel=self.should_cancel)
        self.astar_instance = AStarAlgorithm(self.game_state, weight=5.0, should_cancel=self.should_cancel)
        
        self._handlers = {
            "BFS": self.bfs_instance.search,
            "DFS": self.dfs_instance.search,
            "UCS": self.ucs_instance.search,
            "A*": self.astar_instance.search,
        }
        
        # Map algorithm names to instances for feedback extraction
        self._instances = {
            "BFS": self.bfs_instance,
            "DFS": self.dfs_instance,
            "UCS": self.ucs_instance,
            "A*": self.astar_instance,
        }

    def search(self, algorithm, heuristic_func=combined_heuristic):
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
    
    def get_algorithm_instance(self, algorithm: str):
        """Get the algorithm instance for a given algorithm name.
        
        Args:
            algorithm: Algorithm key (e.g. "BFS", "DFS", "UCS", "A*").
            
        Returns:
            The algorithm instance or None if not found.
        """
        return self._instances.get(algorithm)
