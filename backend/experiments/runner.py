"""Experiment runner for evaluating BFS and DFS on multiple FreeCell deals.

This script:
1. Generates or loads multiple FreeCell deals
2. Runs BFS and DFS on each deal
3. Collects metrics (time, memory, nodes, solution length)
4. Saves results to JSON and CSV for analysis

Usage:
    python -m backend.experiments.runner --deals 10 --output results.json
"""

import json
import csv
import sys
import time
from pathlib import Path
from typing import List, Optional
import argparse

from backend.model.state import State
from backend.engine.shuffle import microsoft_shuffled_deck
from backend.search.bfs import BFSAlgorithm
from backend.search.dfs import DFSAlgorithm
from backend.search.instrumentation import SearchMetrics


def create_initial_state(deal_number: int) -> State:
    """Create initial FreeCell State from deal number.
    
    Args:
        deal_number: Microsoft FreeCell deal number.
    
    Returns:
        State: Initial game state with cards distributed to tableau.
    """
    # Get shuffled deck using Microsoft FreeCell algorithm
    shuffled_deck = microsoft_shuffled_deck(deal_number)
    
    # Distribute cards across 8 tableau columns
    # Cards 0-6 go to columns 0-6, cards 7-13 cycle back, etc.
    tableau = [[] for _ in range(8)]
    for i, card in enumerate(shuffled_deck):
        tableau[i % 8].append(card)
    
    # Convert to tuples
    tableau = tuple(tuple(col) for col in tableau)
    
    # Empty freecells (4 slots)
    freecells = (None, None, None, None)
    
    # Empty foundations (4 stacks, one per suit)
    foundations = ((), (), (), ())
    
    return State(tableau=tableau, freecells=freecells, foundations=foundations)


class ExperimentRunner:
    """Harness for running search algorithms across multiple test cases."""
    
    def __init__(self, num_deals: int = 5, random_seed: Optional[int] = 42):
        """Initialize experiment runner.
        
        Args:
            num_deals: Number of FreeCell deals to test.
            random_seed: Random seed for reproducible shuffle (if applicable).
        """
        self.num_deals = num_deals
        self.random_seed = random_seed
        self.results: List[dict] = []
    
    def generate_test_cases(self) -> List[State]:
        """Generate multiple FreeCell initial states.
        
        For reproducibility, uses fixed seed. Generates classic Microsoft FreeCell
        deals numbered 1 onwards.
        
        Returns:
            List[State]: Initial states for testing.
        """
        test_states = []
        
        # Generate deals using Microsoft FreeCell deal numbers
        for i in range(self.num_deals):
            try:
                # Deal numbers start from 1
                deal_number = self.random_seed + i if self.random_seed else 1 + i
                state = create_initial_state(deal_number)
                test_states.append(state)
            except Exception as e:
                print(f"Warning: Could not generate deal {i}: {e}", file=sys.stderr)
        
        return test_states
    
    def run_bfs(self, state: State) -> tuple[Optional[List], Optional[SearchMetrics]]:
        """Run BFS on a single deal.
        
        Args:
            state: Initial game state.
        
        Returns:
            Tuple of (solution path, metrics).
        """
        bfs = BFSAlgorithm(state, collect_metrics=True)
        solution = bfs.search()
        metrics = bfs.get_metrics()
        return solution, metrics
    
    def run_dfs(self, state: State) -> tuple[Optional[List], Optional[SearchMetrics]]:
        """Run DFS on a single deal.
        
        Args:
            state: Initial game state.
        
        Returns:
            Tuple of (solution path, metrics).
        """
        dfs = DFSAlgorithm(state, collect_metrics=True)
        solution = dfs.search()
        metrics = dfs.get_metrics()
        return solution, metrics
    
    def run_experiment(self) -> List[dict]:
        """Run full experiment suite.
        
        Returns:
            List of result dictionaries (one per deal per algorithm).
        """
        self.results = []
        test_cases = self.generate_test_cases()
        
        print(f"Running experiments on {len(test_cases)} deals...", file=sys.stderr)
        
        for deal_idx, state in enumerate(test_cases):
            print(f"\n[Deal {deal_idx + 1}/{len(test_cases)}]", file=sys.stderr)
            
            # Run BFS
            print("  Running BFS...", end=" ", file=sys.stderr, flush=True)
            try:
                bfs_solution, bfs_metrics = self.run_bfs(state)
                if bfs_metrics:
                    result_bfs = bfs_metrics.to_dict()
                    result_bfs["deal_id"] = deal_idx
                    self.results.append(result_bfs)
                    print(f"OK ({bfs_metrics.solution_length} moves, {bfs_metrics.time_seconds:.2f}s)", 
                          file=sys.stderr)
                else:
                    print("FAILED (no metrics)", file=sys.stderr)
            except Exception as e:
                print(f"ERROR: {e}", file=sys.stderr)
            
            # Run DFS
            print("  Running DFS...", end=" ", file=sys.stderr, flush=True)
            try:
                dfs_solution, dfs_metrics = self.run_dfs(state)
                if dfs_metrics:
                    result_dfs = dfs_metrics.to_dict()
                    result_dfs["deal_id"] = deal_idx
                    self.results.append(result_dfs)
                    print(f"OK ({dfs_metrics.solution_length} moves, {dfs_metrics.time_seconds:.2f}s)", 
                          file=sys.stderr)
                else:
                    print("FAILED (no metrics)", file=sys.stderr)
            except Exception as e:
                print(f"ERROR: {e}", file=sys.stderr)
        
        return self.results
    
    def save_json(self, filepath: str):
        """Save results to JSON.
        
        Args:
            filepath: Output JSON file path.
        """
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"Results saved to {filepath}", file=sys.stderr)
    
    def save_csv(self, filepath: str):
        """Save results to CSV.
        
        Args:
            filepath: Output CSV file path.
        """
        if not self.results:
            print("No results to save", file=sys.stderr)
            return
        
        keys = self.results[0].keys()
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.results)
        print(f"Results saved to {filepath}", file=sys.stderr)
    
    def print_summary(self):
        """Print summary statistics."""
        if not self.results:
            print("No results to summarize", file=sys.stderr)
            return
        
        print("\n" + "="*70, file=sys.stderr)
        print("EXPERIMENT SUMMARY", file=sys.stderr)
        print("="*70, file=sys.stderr)
        
        # Separate by algorithm
        bfs_results = [r for r in self.results if r["algorithm"] == "BFS"]
        dfs_results = [r for r in self.results if r["algorithm"] == "DFS"]
        
        for algo_name, results in [("BFS", bfs_results), ("DFS", dfs_results)]:
            if not results:
                continue
            
            print(f"\n{algo_name}:", file=sys.stderr)
            print(f"  Deals completed: {len(results)}/{self.num_deals}", file=sys.stderr)
            
            successful = [r for r in results if r["solution_length"] > 0]
            print(f"  Successful: {len(successful)}/{len(results)}", file=sys.stderr)
            
            if successful:
                avg_time = sum(r["time_seconds"] for r in successful) / len(successful)
                avg_memory = sum(r["peak_memory_mb"] for r in successful) / len(successful)
                avg_nodes = sum(r["expanded_nodes"] for r in successful) / len(successful)
                avg_length = sum(r["solution_length"] for r in successful) / len(successful)
                
                print(f"  Avg time: {avg_time:.3f}s", file=sys.stderr)
                print(f"  Avg memory: {avg_memory:.1f}MB", file=sys.stderr)
                print(f"  Avg expanded nodes: {avg_nodes:.0f}", file=sys.stderr)
                print(f"  Avg solution length: {avg_length:.1f} moves", file=sys.stderr)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run FreeCell solver experiments comparing BFS and DFS"
    )
    parser.add_argument(
        "--deals", type=int, default=5,
        help="Number of FreeCell deals to test (default: 5)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    parser.add_argument(
        "--output", type=str, default="experiment_results.json",
        help="Output file (will save both .json and .csv, default: experiment_results)"
    )
    
    args = parser.parse_args()
    
    runner = ExperimentRunner(num_deals=args.deals, random_seed=args.seed)
    results = runner.run_experiment()
    runner.print_summary()
    
    # Save results
    output_base = Path(args.output).stem
    runner.save_json(f"{output_base}.json")
    runner.save_csv(f"{output_base}.csv")
    
    print(f"\nTotal results collected: {len(results)}", file=sys.stderr)


if __name__ == "__main__":
    main()
