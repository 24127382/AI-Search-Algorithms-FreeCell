"""Instrumentation for collecting search algorithm metrics."""

import json
import tracemalloc
from dataclasses import dataclass, asdict
from typing import Optional, List


@dataclass
class SearchMetrics:
    """Performance metrics for a single search run.
    
    Attributes:
        algorithm: Name of the algorithm (BFS, DFS, etc.)
        time_seconds: Total execution time in seconds.
        peak_memory_mb: Peak memory in MB (measured via tracemalloc).
        expanded_nodes: Total number of states expanded.
        solution_length: Number of moves in final solution (or -1 if no solution).
        frontier_max_size: Maximum frontier/stack size during search.
    
    Invariants:
        - solution_length >= 1 if solution found, -1 otherwise.
        - expanded_nodes >= 1 (at least initial state).
        - All numeric fields >= 0.
    """
    
    algorithm: str
    time_seconds: float
    peak_memory_mb: float
    expanded_nodes: int
    solution_length: int
    frontier_max_size: int
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    def __repr__(self) -> str:
        """Summary representation for inspection."""
        status = f"{self.solution_length} moves" if self.solution_length > 0 else "NO SOLUTION"
        return (f"{self.__class__.__name__}("
                f"algorithm={self.algorithm}, "
                f"time={self.time_seconds:.2f}s, "
                f"memory={self.peak_memory_mb:.1f}MB, "
                f"nodes={self.expanded_nodes}, "
                f"solution={status})")


class MetricsCollector:
    """Context manager for collecting search metrics.
    
    IMPORTANT: This collector uses tracemalloc to measure memory. However:
    - Peak memory reported may be slightly higher due to Python's memory allocation
    - The visited set and frontier/stack are the primary memory consumers
    - Hash values (int) are negligible compared to State objects
    
    Usage:
        collector = MetricsCollector()
        with collector:
            result = bfs_algorithm.search()
        metrics = collector.get_metrics("BFS", solution_length=len(result))
    """
    
    def __init__(self):
        """Initialize collector."""
        self.peak_memory = 0
        self.start_memory = 0
        self.expanded_nodes_count = 0
        self.frontier_max = 0
        self._tracemalloc_started = False
    
    def __enter__(self):
        """Start memory tracking."""
        tracemalloc.start()
        self._tracemalloc_started = True
        self.start_memory = tracemalloc.get_traced_memory()[0]
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop memory tracking and compute peak."""
        if self._tracemalloc_started:
            current, peak = tracemalloc.get_traced_memory()
            self.peak_memory = (peak - self.start_memory) / (1024 * 1024)  # Convert to MB
            tracemalloc.stop()
        return False
    
    def record_expansion(self, frontier_size: int):
        """Record an expansion event.
        
        Args:
            frontier_size: Current size of frontier/stack.
        """
        self.expanded_nodes_count += 1
        self.frontier_max = max(self.frontier_max, frontier_size)
    
    def get_metrics(
        self,
        algorithm: str,
        time_seconds: float,
        solution_length: Optional[int] = None
    ) -> SearchMetrics:
        """Construct metrics object from collected data.
        
        Args:
            algorithm: Name of algorithm.
            time_seconds: Execution time in seconds.
            solution_length: Length of solution path (-1 if no solution).
        
        Returns:
            SearchMetrics: Collected metrics.
        """
        if solution_length is None:
            solution_length = -1
        
        return SearchMetrics(
            algorithm=algorithm,
            time_seconds=time_seconds,
            peak_memory_mb=max(0, self.peak_memory),
            expanded_nodes=self.expanded_nodes_count,
            solution_length=solution_length,
            frontier_max_size=self.frontier_max
        )
