#!/usr/bin/env python3
"""Analysis and visualization of Zobrist vs. Bit-Packing benchmark results.

Generates graphs and comprehensive analysis of the benchmark data.
"""

import json
from pathlib import Path
from typing import Dict, List, Any
import statistics

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend


def load_benchmark_results(filepath: str = "experiment_logs/zobrist_benchmark.json") -> Dict[str, Any]:
    """Load benchmark results from JSON file.
    
    Args:
        filepath: Path to benchmark results JSON.
    
    Returns:
        dict: Parsed benchmark data.
    """
    with open(filepath, "r") as f:
        return json.load(f)


def analyze_hash_efficiency(results: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze hash computation efficiency.
    
    Args:
        results: Benchmark results dictionary.
    
    Returns:
        dict: Analysis results.
    """
    deals = results["deals"]
    
    bp_hash_times = []
    zob_hash_times = []
    bp_hash_per_node = []
    zob_hash_per_node = []
    
    for deal_result in deals:
        bp = deal_result["bit_packing"]
        zob = deal_result["zobrist"]
        
        if bp["nodes_expanded"] > 0:
            bp_hash_per_node.append(
                bp["hash_total_time_ms"] / bp["hash_computations"] 
                if bp["hash_computations"] > 0 else 0
            )
        
        if zob["nodes_expanded"] > 0:
            zob_hash_per_node.append(
                zob["hash_total_time_ms"] / zob["hash_computations"]
                if zob["hash_computations"] > 0 else 0
            )
    
    return {
        "bp_avg_hash_per_computation_us": statistics.mean(bp_hash_per_node) * 1000 if bp_hash_per_node else 0,
        "zob_avg_hash_per_computation_us": statistics.mean(zob_hash_per_node) * 1000 if zob_hash_per_node else 0,
        "bp_total_hash_calls": sum(d["bit_packing"]["hash_computations"] for d in deals),
        "zob_total_hash_calls": sum(d["zobrist"]["hash_computations"] for d in deals),
    }


def plot_timing_comparison(results: Dict[str, Any], output_file: str = "plots/timing_comparison.png"):
    """Create timing comparison graph.
    
    Args:
        results: Benchmark results.
        output_file: Output PNG path.
    """
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    deals = results["deals"]
    deal_nums = [d["deal"] for d in deals]
    bp_times = [d["bit_packing"]["elapsed_ms"] for d in deals]
    zob_times = [d["zobrist"]["elapsed_ms"] for d in deals]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Absolute timing
    ax1.plot(deal_nums, bp_times, "b-o", label="Bit-Packing", linewidth=2, markersize=5)
    ax1.plot(deal_nums, zob_times, "r-s", label="Zobrist (Full Recompute)", linewidth=2, markersize=5)
    ax1.set_xlabel("Deal Number", fontsize=12)
    ax1.set_ylabel("Total Time (ms)", fontsize=12)
    ax1.set_title("A* Search Time: Bit-Packing vs. Zobrist", fontsize=13, fontweight="bold")
    ax1.legend(fontsize=11)
    ax1.grid(True, alpha=0.3)
    
    # Relative timing
    speedups = [bp / zob if zob > 0 else 0 for bp, zob in zip(bp_times, zob_times)]
    colors = ["green" if s > 1 else "red" for s in speedups]
    ax2.bar(deal_nums, speedups, color=colors, alpha=0.7, width=0.6)
    ax2.axhline(y=1.0, color="black", linestyle="--", linewidth=2, label="Parity (1.0x)")
    ax2.set_xlabel("Deal Number", fontsize=12)
    ax2.set_ylabel("Speedup Factor (BP / Zobrist)", fontsize=12)
    ax2.set_title("Bit-Packing Speedup over Zobrist", fontsize=13, fontweight="bold")
    ax2.legend(fontsize=11)
    ax2.grid(True, alpha=0.3, axis="y")
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"Saved: {output_file}")


def plot_hash_computations(results: Dict[str, Any], output_file: str = "plots/hash_computations.png"):
    """Create hash computation count comparison.
    
    Args:
        results: Benchmark results.
        output_file: Output PNG path.
    """
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    deals = results["deals"]
    deal_nums = [d["deal"] for d in deals]
    bp_hashes = [d["bit_packing"]["hash_computations"] for d in deals]
    zob_hashes = [d["zobrist"]["hash_computations"] for d in deals]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Hash computations
    x = range(len(deal_nums))
    width = 0.35
    ax1.bar([i - width/2 for i in x], bp_hashes, width, label="Bit-Packing", alpha=0.8)
    ax1.bar([i + width/2 for i in x], zob_hashes, width, label="Zobrist", alpha=0.8)
    ax1.set_xlabel("Deal Number", fontsize=12)
    ax1.set_ylabel("Number of Hash Computations", fontsize=12)
    ax1.set_title("Hash Function Call Counts", fontsize=13, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(deal_nums)
    ax1.legend(fontsize=11)
    ax1.grid(True, alpha=0.3, axis="y")
    
    # Hash ratio
    ratios = [zob / bp if bp > 0 else 0 for bp, zob in zip(bp_hashes, zob_hashes)]
    ax2.plot(deal_nums, ratios, "mo-", linewidth=2, markersize=7)
    ax2.set_xlabel("Deal Number", fontsize=12)
    ax2.set_ylabel("Zobrist:Bit-Packing Hash Ratio", fontsize=12)
    ax2.set_title("Relative Hash Computation Overhead", fontsize=13, fontweight="bold")
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"Saved: {output_file}")


def plot_nodes_expanded(results: Dict[str, Any], output_file: str = "plots/nodes_expanded.png"):
    """Create nodes expanded comparison.
    
    Args:
        results: Benchmark results.
        output_file: Output PNG path.
    """
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    deals = results["deals"]
    deal_nums = [d["deal"] for d in deals]
    bp_nodes = [d["bit_packing"]["nodes_expanded"] for d in deals]
    zob_nodes = [d["zobrist"]["nodes_expanded"] for d in deals]
    
    fig, ax = plt.subplots(figsize=(12, 5))
    
    x = range(len(deal_nums))
    width = 0.35
    ax.bar([i - width/2 for i in x], bp_nodes, width, label="Bit-Packing", alpha=0.8)
    ax.bar([i + width/2 for i in x], zob_nodes, width, label="Zobrist", alpha=0.8)
    ax.set_xlabel("Deal Number", fontsize=12)
    ax.set_ylabel("Nodes Expanded", fontsize=12)
    ax.set_title("Search Space Explored: Bit-Packing vs. Zobrist", fontsize=13, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(deal_nums)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3, axis="y")
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"Saved: {output_file}")


def plot_hash_cost_per_node(results: Dict[str, Any], output_file: str = "plots/hash_cost_per_node.png"):
    """Create hash cost per node comparison.
    
    Args:
        results: Benchmark results.
        output_file: Output PNG path.
    """
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    deals = results["deals"]
    deal_nums = [d["deal"] for d in deals]
    bp_cost_per_node = []
    zob_cost_per_node = []
    
    for d in deals:
        bp = d["bit_packing"]
        zob = d["zobrist"]
        
        if bp["nodes_expanded"] > 0:
            bp_cost = (bp["hash_total_time_ms"] / bp["hash_computations"]) * 1000 if bp["hash_computations"] > 0 else 0
            bp_cost_per_node.append(bp_cost)
        else:
            bp_cost_per_node.append(0)
        
        if zob["nodes_expanded"] > 0:
            zob_cost = (zob["hash_total_time_ms"] / zob["hash_computations"]) * 1000 if zob["hash_computations"] > 0 else 0
            zob_cost_per_node.append(zob_cost)
        else:
            zob_cost_per_node.append(0)
    
    fig, ax = plt.subplots(figsize=(12, 5))
    
    ax.plot(deal_nums, bp_cost_per_node, "b-o", label="Bit-Packing", linewidth=2, markersize=6)
    ax.plot(deal_nums, zob_cost_per_node, "r-s", label="Zobrist", linewidth=2, markersize=6)
    ax.set_xlabel("Deal Number", fontsize=12)
    ax.set_ylabel("Hash Cost per Computation (microseconds)", fontsize=12)
    ax.set_title("Hash Computation Overhead", fontsize=13, fontweight="bold")
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"Saved: {output_file}")


def main():
    # Load results
    print("Loading benchmark results...")
    results = load_benchmark_results()
    
    # Analysis
    print("\n" + "="*60)
    print("BENCHMARK ANALYSIS")
    print("="*60)
    
    hash_analysis = analyze_hash_efficiency(results)
    print(f"\nHash Efficiency Analysis:")
    print(f"  Bit-Packing avg cost per hash:  {hash_analysis['bp_avg_hash_per_computation_us']:.4f} µs")
    print(f"  Zobrist avg cost per hash:      {hash_analysis['zob_avg_hash_per_computation_us']:.4f} µs")
    print(f"  Bit-Packing total hash calls:   {hash_analysis['bp_total_hash_calls']:,}")
    print(f"  Zobrist total hash calls:       {hash_analysis['zob_total_hash_calls']:,}")
    
    agg = results.get("aggregate", {})
    print(f"\nPerformance Aggregate:")
    print(f"  Speedup factor (BP / Zobrist): {agg.get('speedup_factor', 0):.3f}x")
    print(f"  Average time BP:  {agg.get('avg_time_ms_bp', 0):.2f} ms")
    print(f"  Average time Zob: {agg.get('avg_time_ms_zobrist', 0):.2f} ms")
    
    # Generate visualizations
    print("\nGenerating visualizations...")
    plot_timing_comparison(results)
    plot_hash_computations(results)
    plot_nodes_expanded(results)
    plot_hash_cost_per_node(results)
    
    print("\n" + "="*60)
    print("Analysis complete!")
    print("="*60)


if __name__ == "__main__":
    main()
