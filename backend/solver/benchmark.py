"""Benchmark framework for Zobrist vs. Bit-Packing hash comparison.

This module runs controlled experiments comparing two A* implementations:
1. Bit-packing hash (baseline) — uses State.board_code
2. Zobrist hash (target) — uses incremental XOR updates

Experiments are run on standard FreeCell deals with identical parameters.
"""

import json
from pathlib import Path
from typing import List, Dict, Any
import time

from backend.engine.shuffle import deal_by_game_number
from backend.model.state import State
from backend.solver.astar_bit_packing import AStarBitPackingHash
from backend.solver.astar_zobrist import AStarZobristHash
from backend.solver.zobrist import ZobristTable
from backend.solver.heuristics import combined_heuristic


class BenchmarkExperiment:
    """Controller for running a single benchmark trial.
    
    Runs both A* implementations on the same FreeCell deal with
    identical heuristic and weight settings. Collects detailed metrics.
    """

    def __init__(
        self,
        deal_number: int,
        weight: float = 5.0,
        heuristic_func = None,
        zobrist_table: ZobristTable = None,
    ):
        """Initialize benchmark for a specific deal.
        
        Args:
            deal_number: FreeCell game number (seed).
            weight: A* weight factor (inflation of heuristic).
            heuristic_func: h(state) -> int function.
            zobrist_table: Shared Zobrist table for consistency.
        """
        self.deal_number = deal_number
        self.weight = weight
        self.heuristic_func = heuristic_func or combined_heuristic
        self.zobrist_table = zobrist_table or ZobristTable(seed=42)
        self.initial_state = self._load_deal()

    def _load_deal(self) -> State:
        """Load initial board state from deal number.
        
        Returns:
            State: Initial FreeCell configuration.
        """
        tableau = deal_by_game_number(self.deal_number)
        freecells = (None, None, None, None)
        foundations = ((), (), (), ())
        
        return State(
            tableau=tuple(tuple(col) for col in tableau),
            freecells=freecells,
            foundations=foundations,
        )

    def run_bit_packing(self, max_nodes: int = 1000000) -> Dict[str, Any]:
        """Run A* with bit-packing baseline.
        
        Args:
            max_nodes: Maximum nodes to expand (safety limit).
        
        Returns:
            dict: Statistics from the search.
        """
        cancelled = False
        expanded_count = 0
        
        def should_cancel():
            nonlocal expanded_count, cancelled
            if expanded_count >= max_nodes:
                cancelled = True
                return True
            return False
        
        solver = AStarBitPackingHash(
            self.initial_state,
            heuristic_func=self.heuristic_func,
            weight=self.weight,
            should_cancel=should_cancel,
        )
        
        # Monkey-patch to track expanded nodes
        original_search = solver.search
        
        def wrapped_search():
            result = original_search()
            stats = solver.last_run_stats
            expanded_count = stats.get("nodes_expanded", 0)
            return result
        
        solver.search = wrapped_search
        solution, stats = solver.search()
        
        return {
            "method": "bit_packing",
            "deal": self.deal_number,
            "weight": self.weight,
            **stats,
        }

    def run_zobrist(self, max_nodes: int = 1000000) -> Dict[str, Any]:
        """Run A* with Zobrist hashing.
        
        Args:
            max_nodes: Maximum nodes to expand (safety limit).
        
        Returns:
            dict: Statistics from the search.
        """
        cancelled = False
        
        def should_cancel():
            nonlocal cancelled
            return cancelled
        
        solver = AStarZobristHash(
            self.initial_state,
            zobrist_table=self.zobrist_table,
            heuristic_func=self.heuristic_func,
            weight=self.weight,
            should_cancel=should_cancel,
        )
        
        solution, stats = solver.search()
        
        return {
            "method": "zobrist",
            "deal": self.deal_number,
            "weight": self.weight,
            **stats,
        }

    def run_both(self, max_nodes: int = 1000000) -> Dict[str, Dict[str, Any]]:
        """Run both solvers and return comparison results.
        
        Args:
            max_nodes: Maximum nodes to expand.
        
        Returns:
            dict: Results with 'bit_packing' and 'zobrist' keys.
        """
        print(f"Deal {self.deal_number}...", end=" ", flush=True)
        
        bp_stats = self.run_bit_packing(max_nodes=max_nodes)
        zob_stats = self.run_zobrist(max_nodes=max_nodes)
        
        print(f"OK")
        
        return {
            "deal": self.deal_number,
            "bit_packing": bp_stats,
            "zobrist": zob_stats,
        }


class BenchmarkSuite:
    """Orchestrates a full benchmark suite across multiple deals.
    
    Generates comparison metrics and aggregated statistics.
    """

    def __init__(
        self,
        deals: List[int],
        weight: float = 5.0,
        heuristic_func = None,
    ):
        """Initialize benchmark suite.
        
        Args:
            deals: List of deal numbers to benchmark.
            weight: A* weight factor.
            heuristic_func: h(state) -> int function.
        """
        self.deals = deals
        self.weight = weight
        self.heuristic_func = heuristic_func or combined_heuristic
        self.zobrist_table = ZobristTable(seed=42)  # Shared across all benchmarks
        self.results = []

    def run(self, max_nodes_per_deal: int = 1000000) -> List[Dict[str, Any]]:
        """Run full benchmark suite.
        
        Args:
            max_nodes_per_deal: Max nodes expanded per deal.
        
        Returns:
            List of comparison results for each deal.
        """
        print(f"\n{'='*60}")
        print(f"Benchmark Suite: {len(self.deals)} deals")
        print(f"Weight: {self.weight}, Max nodes: {max_nodes_per_deal}")
        print(f"{'='*60}\n")
        
        for deal_num in self.deals:
            experiment = BenchmarkExperiment(
                deal_num,
                weight=self.weight,
                heuristic_func=self.heuristic_func,
                zobrist_table=self.zobrist_table,
            )
            result = experiment.run_both(max_nodes=max_nodes_per_deal)
            self.results.append(result)
        
        return self.results

    def aggregate_stats(self) -> Dict[str, Any]:
        """Compute aggregate statistics over all benchmark runs.
        
        Returns:
            dict: Aggregated metrics comparing bit-packing vs. Zobrist.
        """
        if not self.results:
            return {}

        bp_times = []
        zob_times = []
        bp_nodes = []
        zob_nodes = []
        bp_hashes = []
        zob_hashes = []
        bp_frontier = []
        zob_frontier = []

        for result in self.results:
            if result["bit_packing"]["solution_found"]:
                bp_times.append(result["bit_packing"]["elapsed_ms"])
                bp_nodes.append(result["bit_packing"]["nodes_expanded"])
                bp_hashes.append(result["bit_packing"]["hash_computations"])
                bp_frontier.append(result["bit_packing"]["frontier_max_size"])

            if result["zobrist"]["solution_found"]:
                zob_times.append(result["zobrist"]["elapsed_ms"])
                zob_nodes.append(result["zobrist"]["nodes_expanded"])
                zob_hashes.append(result["zobrist"]["hash_computations"])
                zob_frontier.append(result["zobrist"]["frontier_max_size"])

        def safe_avg(values):
            return sum(values) / len(values) if values else 0
        
        def safe_sum(values):
            return sum(values) if values else 0

        return {
            "num_deals": len(self.results),
            "num_solved_bp": len(bp_times),
            "num_solved_zobrist": len(zob_times),
            "avg_time_ms_bp": safe_avg(bp_times),
            "avg_time_ms_zobrist": safe_avg(zob_times),
            "total_time_ms_bp": safe_sum(bp_times),
            "total_time_ms_zobrist": safe_sum(zob_times),
            "speedup_factor": safe_avg(bp_times) / safe_avg(zob_times) if safe_avg(zob_times) > 0 else 0,
            "avg_nodes_expanded_bp": safe_avg(bp_nodes),
            "avg_nodes_expanded_zobrist": safe_avg(zob_nodes),
            "avg_hash_computations_bp": safe_avg(bp_hashes),
            "avg_hash_computations_zobrist": safe_avg(zob_hashes),
            "avg_frontier_size_bp": safe_avg(bp_frontier),
            "avg_frontier_size_zobrist": safe_avg(zob_frontier),
        }

    def save_results(self, output_file: str = "benchmark_results.json"):
        """Save detailed benchmark results to JSON.
        
        Args:
            output_file: Path to output JSON file.
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        output_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "weight": self.weight,
            "num_deals": len(self.results),
            "deals": self.results,
            "aggregate": self.aggregate_stats(),
        }
        
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\nResults saved to {output_path}")

    def print_summary(self):
        """Print a human-readable summary of benchmark results."""
        agg = self.aggregate_stats()
        
        if not agg:
            print("No results to summarize.")
            return
        
        print(f"\n{'='*60}")
        print(f"Benchmark Summary")
        print(f"{'='*60}")
        print(f"Deals benchmarked: {agg['num_deals']}")
        print(f"Solved (Bit-Packing): {agg['num_solved_bp']}")
        print(f"Solved (Zobrist): {agg['num_solved_zobrist']}")
        print(f"\n{'Timing (ms)':20} {'Bit-Packing':>15} {'Zobrist':>15}")
        print(f"{'-'*50}")
        print(f"{'Average':20} {agg['avg_time_ms_bp']:>15.2f} {agg['avg_time_ms_zobrist']:>15.2f}")
        print(f"{'Total':20} {agg['total_time_ms_bp']:>15.2f} {agg['total_time_ms_zobrist']:>15.2f}")
        print(f"\n{'Speedup Factor':20} {agg['speedup_factor']:>15.3f}x")
        print(f"\n{'Nodes Expanded':20} {agg['avg_nodes_expanded_bp']:>15.0f} {agg['avg_nodes_expanded_zobrist']:>15.0f}")
        print(f"{'Hash Computations':20} {agg['avg_hash_computations_bp']:>15.0f} {agg['avg_hash_computations_zobrist']:>15.0f}")
        print(f"{'Max Frontier Size':20} {agg['avg_frontier_size_bp']:>15.0f} {agg['avg_frontier_size_zobrist']:>15.0f}")
        print(f"{'='*60}\n")
