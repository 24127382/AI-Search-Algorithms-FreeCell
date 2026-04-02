"""Depth-First Search with detailed experimental logging.

This module provides a DFS implementation optimized for controlled experiments:
- Early stopping on frontier size, expanded nodes, or time limits
- Fine-grained logging at each iteration for visualization
- NO requirement to reach solution (stops when limit hit)
- Global visited set for completeness (graph-search DFS, not tree-search)

IMPORTANT: This is NOT optimized for solver speed—it prioritizes clean data collection.
"""

import time
import json
from typing import List, Optional, Tuple, Dict, Any

from backend.engine.engine import apply_move, get_valid_moves
from backend.model.state import State
from backend.model.move import Move


class DFSExperiment:
    """DFS with experimental stopping conditions and detailed logging."""

    def __init__(
        self,
        initial_state: State,
        max_frontier_size: int = 50000,
        max_expanded_nodes: int = 100000,
        max_time_seconds: float = 30.0,
        log_interval: int = 100
    ):
        """Initialize DFS for experiment.
        
        Args:
            initial_state: Starting game state.
            max_frontier_size: Stop when stack exceeds this size.
            max_expanded_nodes: Stop when nodes expanded exceeds this.
            max_time_seconds: Stop after this many seconds elapsed.
            log_interval: Log every N expansions (set to 1 for every expansion).
        """
        self.initial_state = initial_state
        self.max_frontier_size = max_frontier_size
        self.max_expanded_nodes = max_expanded_nodes
        self.max_time_seconds = max_time_seconds
        self.log_interval = log_interval
        
        # Logs: list of dicts with timing/size data
        self.logs: List[Dict[str, Any]] = []
        self.stop_reason: Optional[str] = None
        self.solution: Optional[List[Move]] = None

    def _estimate_depth(self, parents: dict, current_hash: int) -> int:
        """Estimate current search depth by following parent pointers.
        
        Args:
            parents: Parent pointer mapping.
            current_hash: Hash of current state.
        
        Returns:
            int: Approximate depth (0 for initial state).
        """
        depth = 0
        h = current_hash
        while parents[h][0] is not None:
            depth += 1
            h = parents[h][0]
        return depth

    def search(self) -> Optional[List[Move]]:
        """Execute DFS with early stopping and logging.
        
        Returns:
            List[Move]: Solution if found, None otherwise.
            
        The search will stop due to:
        - Reaching goal (uncommon in experiment mode)
        - Stack size exceeding max_frontier_size
        - Expanded nodes exceeding max_expanded_nodes
        - Elapsed time exceeding max_time_seconds
        
        Stop reason is recorded in self.stop_reason.
        Detailed logs are in self.logs.
        
        NOTE: This is graph-search DFS (with global visited set) to prevent cycles.
        Without visited set, DFS could loop infinitely on reversible moves.
        """
        start_time = time.time()
        
        # Parent pointers: state_hash -> (parent_hash, move)
        parents: dict[int, Tuple[Optional[int], Optional[Move]]] = {}
        
        # State hashes for collision detection
        state_hashes: dict[int, State] = {}
        
        # Global visited set (CRITICAL for completeness: prevents infinite loops)
        visited_hashes = set()
        
        # LIFO stack
        stack = [self.initial_state]
        
        initial_hash = hash(self.initial_state)
        visited_hashes.add(initial_hash)
        state_hashes[initial_hash] = self.initial_state
        parents[initial_hash] = (None, None)
        
        expanded_count = 0
        step_id = 0
        
        while stack:
            # --- CHECK STOPPING CONDITIONS ---
            
            # Time limit
            elapsed = time.time() - start_time
            if elapsed > self.max_time_seconds:
                self.stop_reason = "max_time_exceeded"
                break
            
            # Stack size limit
            if len(stack) > self.max_frontier_size:
                self.stop_reason = "max_frontier_size_exceeded"
                break
            
            # Expanded nodes limit
            if expanded_count >= self.max_expanded_nodes:
                self.stop_reason = "max_expanded_nodes_reached"
                break
            
            # --- EXPAND NEXT STATE ---
            current_state = stack.pop()
            current_hash = hash(current_state)
            expanded_count += 1
            
            # Check goal
            if current_state.is_goal:
                path = self._reconstruct_path(current_hash, parents, state_hashes)
                self.solution = path
                self.stop_reason = "goal_found"
                elapsed = time.time() - start_time
                self._log_step(step_id, elapsed, len(stack), expanded_count, current_hash, parents)
                return path
            
            # --- EXPAND SUCCESSORS ---
            # Push in reverse order so first move is explored first (LIFO)
            valid_moves = get_valid_moves(current_state)
            for move in reversed(valid_moves):
                next_state = apply_move(current_state, move)
                next_hash = hash(next_state)
                
                if next_hash not in visited_hashes:
                    visited_hashes.add(next_hash)
                    state_hashes[next_hash] = next_state
                    parents[next_hash] = (current_hash, move)
                    stack.append(next_state)
            
            # --- LOG AT INTERVALS ---
            if expanded_count % self.log_interval == 0:
                elapsed = time.time() - start_time
                self._log_step(step_id, elapsed, len(stack), expanded_count, current_hash, parents)
                step_id += 1
        
        # No solution found, limit reached
        elapsed = time.time() - start_time
        self._log_step(step_id, elapsed, len(stack), expanded_count, 0, parents)
        return None

    def _log_step(
        self,
        step_id: int,
        elapsed_time: float,
        stack_size: int,
        expanded_nodes: int,
        current_hash: int,
        parents: dict
    ):
        """Record a log entry.
        
        Args:
            step_id: Sequential log step number.
            elapsed_time: Seconds since start.
            stack_size: Current stack size.
            expanded_nodes: Total nodes expanded so far.
            current_hash: Hash of current state (for depth estimation).
            parents: Parent pointer mapping (for depth estimation).
        """
        # Estimate depth
        depth = self._estimate_depth(parents, current_hash) if current_hash in parents else 0
        
        log_entry = {
            "algorithm": "DFS",
            "step": step_id,
            "time": round(elapsed_time, 4),
            "frontier_size": stack_size,
            "expanded_nodes": expanded_nodes,
            "current_depth": depth
        }
        self.logs.append(log_entry)

    @staticmethod
    def _reconstruct_path(
        goal_hash: int,
        parents: dict[int, Tuple[Optional[int], Optional[Move]]],
        state_hashes: dict[int, State]
    ) -> List[Move]:
        """Reconstruct solution by following parent pointers.
        
        Args:
            goal_hash: Hash of goal state.
            parents: Parent pointer mapping.
            state_hashes: Hash -> State mapping.
        
        Returns:
            List[Move]: Solution path in order.
        """
        path = []
        current_hash = goal_hash
        
        while parents[current_hash][0] is not None:
            parent_hash, move = parents[current_hash]
            path.append(move)
            current_hash = parent_hash
        
        path.reverse()
        return path

    def save_logs(self, filepath: str):
        """Save logs to JSON file.
        
        Args:
            filepath: Path to output file.
        """
        data = {
            "algorithm": "DFS",
            "stop_reason": self.stop_reason,
            "solution_found": self.solution is not None,
            "solution_length": len(self.solution) if self.solution else -1,
            "logs": self.logs
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"DFS logs saved to {filepath}")

    def get_logs(self) -> List[Dict[str, Any]]:
        """Return logged data.
        
        Returns:
            List of log entries.
        """
        return self.logs
