"""Visualization of FreeCell solver experiment results using matplotlib.

This script generates publication-quality plots comparing BFS and DFS performance.

Usage:
    python visualization.py --input experiment_results.json --output plots/
"""

import json
import csv
import sys
import argparse
from pathlib import Path
from typing import Dict, List
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np


class ExperimentVisualizer:
    """Generate publication-quality plots from experiment results."""
    
    def __init__(self, results_json: str):
        """Load experiment results from JSON.
        
        Args:
            results_json: Path to JSON file with results.
        """
        with open(results_json, 'r') as f:
            self.results = json.load(f)
        
        self._organize_by_algorithm()
    
    def _organize_by_algorithm(self):
        """Organize results by algorithm."""
        self.bfs_results = [r for r in self.results if r["algorithm"] == "BFS"]
        self.dfs_results = [r for r in self.results if r["algorithm"] == "DFS"]
    
    def plot_nodes_vs_time(self, output_file: str = "nodes_vs_time.png"):
        """Plot expanded nodes vs execution time.
        
        X-axis: Execution time (seconds)
        Y-axis: Expanded nodes (log scale)
        
        This shows the exploring power of each algorithm: steeper slope = more efficient.
        
        Args:
            output_file: Output PNG filename.
        """
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Extract successful runs
        bfs_successful = [r for r in self.bfs_results if r["solution_length"] > 0]
        dfs_successful = [r for r in self.dfs_results if r["solution_length"] > 0]
        
        if bfs_successful:
            times_bfs = [r["time_seconds"] for r in bfs_successful]
            nodes_bfs = [r["expanded_nodes"] for r in bfs_successful]
            ax.scatter(times_bfs, nodes_bfs, s=100, alpha=0.6, label="BFS", color="blue", marker="o")
            # Add deal IDs as annotations
            for i, (t, n) in enumerate(zip(times_bfs, nodes_bfs)):
                ax.annotate(f"D{bfs_successful[i]['deal_id']}", (t, n), fontsize=8, 
                           xytext=(5, 5), textcoords="offset points")
        
        if dfs_successful:
            times_dfs = [r["time_seconds"] for r in dfs_successful]
            nodes_dfs = [r["expanded_nodes"] for r in dfs_successful]
            ax.scatter(times_dfs, nodes_dfs, s=100, alpha=0.6, label="DFS", color="red", marker="^")
            # Add deal IDs as annotations
            for i, (t, n) in enumerate(zip(times_dfs, nodes_dfs)):
                ax.annotate(f"D{dfs_successful[i]['deal_id']}", (t, n), fontsize=8, 
                           xytext=(5, 5), textcoords="offset points")
        
        ax.set_xlabel("Execution Time (seconds)", fontsize=12)
        ax.set_ylabel("Expanded Nodes (log scale)", fontsize=12)
        ax.set_title("Search Efficiency: Expanded Nodes vs Execution Time", fontsize=14, fontweight="bold")
        ax.set_yscale("log")
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3, which="both")
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"Saved: {output_file}", file=sys.stderr)
        plt.close()
    
    def plot_memory_comparison(self, output_file: str = "memory_comparison.png"):
        """Bar chart comparing peak memory usage.
        
        Groups by algorithm and shows average memory with error bars.
        
        Args:
            output_file: Output PNG filename.
        """
        fig, ax = plt.subplots(figsize=(8, 6))
        
        bfs_successful = [r for r in self.bfs_results if r["solution_length"] > 0]
        dfs_successful = [r for r in self.dfs_results if r["solution_length"] > 0]
        
        algorithms = []
        memories = []
        errors = []
        
        if bfs_successful:
            bfs_mems = [r["peak_memory_mb"] for r in bfs_successful]
            algorithms.append("BFS")
            memories.append(np.mean(bfs_mems))
            errors.append(np.std(bfs_mems))
        
        if dfs_successful:
            dfs_mems = [r["peak_memory_mb"] for r in dfs_successful]
            algorithms.append("DFS")
            memories.append(np.mean(dfs_mems))
            errors.append(np.std(dfs_mems))
        
        colors = ["blue" if algo == "BFS" else "red" for algo in algorithms]
        bars = ax.bar(algorithms, memories, yerr=errors, capsize=10, 
                     color=colors, alpha=0.6, edgecolor="black", linewidth=1.5)
        
        ax.set_ylabel("Peak Memory Usage (MB)", fontsize=12)
        ax.set_title("Memory Consumption Comparison", fontsize=14, fontweight="bold")
        ax.grid(True, alpha=0.3, axis="y")
        
        # Add value labels on bars
        for bar, mem in zip(bars, memories):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f"{mem:.1f} MB", ha="center", va="bottom", fontsize=11, fontweight="bold")
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"Saved: {output_file}", file=sys.stderr)
        plt.close()
    
    def plot_solution_length_comparison(self, output_file: str = "solution_length_comparison.png"):
        """Bar chart comparing solution length (moves).
        
        Args:
            output_file: Output PNG filename.
        """
        fig, ax = plt.subplots(figsize=(8, 6))
        
        bfs_successful = [r for r in self.bfs_results if r["solution_length"] > 0]
        dfs_successful = [r for r in self.dfs_results if r["solution_length"] > 0]
        
        algorithms = []
        lengths = []
        errors = []
        
        if bfs_successful:
            bfs_lens = [r["solution_length"] for r in bfs_successful]
            algorithms.append("BFS")
            lengths.append(np.mean(bfs_lens))
            errors.append(np.std(bfs_lens))
        
        if dfs_successful:
            dfs_lens = [r["solution_length"] for r in dfs_successful]
            algorithms.append("DFS")
            lengths.append(np.mean(dfs_lens))
            errors.append(np.std(dfs_lens))
        
        colors = ["blue" if algo == "BFS" else "red" for algo in algorithms]
        bars = ax.bar(algorithms, lengths, yerr=errors, capsize=10,
                     color=colors, alpha=0.6, edgecolor="black", linewidth=1.5)
        
        ax.set_ylabel("Solution Length (moves)", fontsize=12)
        ax.set_title("Solution Quality Comparison", fontsize=14, fontweight="bold")
        ax.grid(True, alpha=0.3, axis="y")
        
        # Add value labels on bars
        for bar, length in zip(bars, lengths):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f"{length:.1f}", ha="center", va="bottom", fontsize=11, fontweight="bold")
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"Saved: {output_file}", file=sys.stderr)
        plt.close()
    
    def plot_frontier_size_comparison(self, output_file: str = "frontier_size_comparison.png"):
        """Bar chart comparing maximum frontier/stack size.
        
        Lower is better (less memory pressure during search).
        
        Args:
            output_file: Output PNG filename.
        """
        fig, ax = plt.subplots(figsize=(8, 6))
        
        bfs_successful = [r for r in self.bfs_results if r["solution_length"] > 0]
        dfs_successful = [r for r in self.dfs_results if r["solution_length"] > 0]
        
        algorithms = []
        frontier_sizes = []
        errors = []
        
        if bfs_successful:
            bfs_frontier = [r["frontier_max_size"] for r in bfs_successful]
            algorithms.append("BFS")
            frontier_sizes.append(np.mean(bfs_frontier))
            errors.append(np.std(bfs_frontier))
        
        if dfs_successful:
            dfs_frontier = [r["frontier_max_size"] for r in dfs_successful]
            algorithms.append("DFS")
            frontier_sizes.append(np.mean(dfs_frontier))
            errors.append(np.std(dfs_frontier))
        
        colors = ["blue" if algo == "BFS" else "red" for algo in algorithms]
        bars = ax.bar(algorithms, frontier_sizes, yerr=errors, capsize=10,
                     color=colors, alpha=0.6, edgecolor="black", linewidth=1.5)
        
        ax.set_ylabel("Max Frontier/Stack Size (nodes)", fontsize=12)
        ax.set_title("Maximum Search Frontier Comparison", fontsize=14, fontweight="bold")
        ax.set_yscale("log")
        ax.grid(True, alpha=0.3, axis="y", which="both")
        
        # Add value labels on bars
        for bar, size in zip(bars, frontier_sizes):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f"{size:.0f}", ha="center", va="bottom", fontsize=11, fontweight="bold")
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"Saved: {output_file}", file=sys.stderr)
        plt.close()
    
    def plot_all(self, output_dir: str = "plots"):
        """Generate all plots.
        
        Args:
            output_dir: Directory to save plots.
        """
        Path(output_dir).mkdir(exist_ok=True)
        
        self.plot_nodes_vs_time(f"{output_dir}/nodes_vs_time.png")
        self.plot_memory_comparison(f"{output_dir}/memory_comparison.png")
        self.plot_solution_length_comparison(f"{output_dir}/solution_length_comparison.png")
        self.plot_frontier_size_comparison(f"{output_dir}/frontier_size_comparison.png")
    
    def print_summary_table(self):
        """Print summary statistics as a formatted table."""
        print("\n" + "="*90, file=sys.stderr)
        print("DETAILED EXPERIMENT SUMMARY", file=sys.stderr)
        print("="*90, file=sys.stderr)
        
        for algo_name, results in [("BFS", self.bfs_results), ("DFS", self.dfs_results)]:
            successful = [r for r in results if r["solution_length"] > 0]
            print(f"\n{algo_name}:", file=sys.stderr)
            print(f"  Completed: {len(successful)}/{len(results)}", file=sys.stderr)
            
            if successful:
                print(f"  {'Deal':<5} {'Time(s)':<10} {'Memory(MB)':<12} {'Nodes':<10} {'Solution':<10}", 
                      file=sys.stderr)
                print("  " + "-"*60, file=sys.stderr)
                for r in successful:
                    print(f"  {r['deal_id']:<5} {r['time_seconds']:<10.3f} "
                          f"{r['peak_memory_mb']:<12.1f} {r['expanded_nodes']:<10} "
                          f"{r['solution_length']:<10}",
                          file=sys.stderr)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate publication-quality plots from FreeCell solver experiments"
    )
    parser.add_argument(
        "--input", type=str, required=True,
        help="Input JSON file with experiment results"
    )
    parser.add_argument(
        "--output", type=str, default="plots",
        help="Output directory for PNG plots (default: plots/)"
    )
    
    args = parser.parse_args()
    
    if not Path(args.input).exists():
        print(f"Error: {args.input} not found", file=sys.stderr)
        sys.exit(1)
    
    visualizer = ExperimentVisualizer(args.input)
    visualizer.print_summary_table()
    visualizer.plot_all(args.output)
    
    print(f"\nAll plots saved to: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
