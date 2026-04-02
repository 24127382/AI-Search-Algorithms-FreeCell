#!/usr/bin/env python3
"""Visualization for BFS vs DFS experiment logs.

This script generates 3 required charts from experiment JSON logs:
1. Frontier Growth (log scale Y-axis)
2. Expanded Nodes vs Time
3. Efficiency Trade-off (Scatter: frontier_size vs expanded_nodes)

Usage:
    python plot_experiment.py --input-dir experiment_logs --output-dir plots
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


def load_logs(log_file: str) -> Dict[str, Any]:
    """Load JSON log file.
    
    Args:
        log_file: Path to JSON log.
    
    Returns:
        dict: Parsed log data.
    """
    with open(log_file, 'r') as f:
        return json.load(f)


def plot_frontier_growth(
    bfs_logs: List[Dict],
    dfs_logs: List[Dict],
    output_file: str,
    title: str = "Frontier Size Growth Over Time (BFS vs DFS)"
):
    """Chart 1: Frontier size over time with log scale Y-axis.
    
    Args:
        bfs_logs: List of BFS log entries.
        dfs_logs: List of DFS log entries.
        output_file: Output PNG file path.
        title: Chart title.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Extract data
    bfs_times = [log["time"] for log in bfs_logs]
    bfs_frontiers = [log["frontier_size"] for log in bfs_logs]
    
    dfs_times = [log["time"] for log in dfs_logs]
    dfs_frontiers = [log["frontier_size"] for log in dfs_logs]
    
    # Plot
    ax.plot(bfs_times, bfs_frontiers, marker='o', linestyle='-', linewidth=2,
            markersize=4, label='BFS', color='#1f77b4')
    ax.plot(dfs_times, dfs_frontiers, marker='s', linestyle='-', linewidth=2,
            markersize=4, label='DFS', color='#ff7f0e')
    
    # Formatting
    ax.set_xlabel('Time (seconds)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Frontier Size', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold')
    
    # Log scale for Y-axis
    ax.set_yscale('log')
    
    # Grid
    ax.grid(True, which='both', alpha=0.3)
    ax.legend(fontsize=11, loc='best')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    print(f"✓ Chart 1 saved: {output_file}")
    plt.close()


def plot_expanded_nodes_vs_time(
    bfs_logs: List[Dict],
    dfs_logs: List[Dict],
    output_file: str,
    title: str = "Nodes Expanded Over Time (BFS vs DFS)"
):
    """Chart 2: Expanded nodes vs time.
    
    Args:
        bfs_logs: List of BFS log entries.
        dfs_logs: List of DFS log entries.
        output_file: Output PNG file path.
        title: Chart title.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Extract data
    bfs_times = [log["time"] for log in bfs_logs]
    bfs_expanded = [log["expanded_nodes"] for log in bfs_logs]
    
    dfs_times = [log["time"] for log in dfs_logs]
    dfs_expanded = [log["expanded_nodes"] for log in dfs_logs]
    
    # Plot
    ax.plot(bfs_times, bfs_expanded, marker='o', linestyle='-', linewidth=2,
            markersize=4, label='BFS', color='#1f77b4')
    ax.plot(dfs_times, dfs_expanded, marker='s', linestyle='-', linewidth=2,
            markersize=4, label='DFS', color='#ff7f0e')
    
    # Formatting
    ax.set_xlabel('Time (seconds)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Nodes Expanded', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold')
    
    # Grid
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=11, loc='best')
    
    # Format Y-axis with commas
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f'{int(x):,}'))
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    print(f"✓ Chart 2 saved: {output_file}")
    plt.close()


def plot_efficiency_tradeoff(
    bfs_logs: List[Dict],
    dfs_logs: List[Dict],
    output_file: str,
    title: str = "Efficiency Trade-off: Frontier vs Nodes Expanded"
):
    """Chart 3: Scatter plot of frontier_size vs expanded_nodes.
    
    This shows how BFS expands fewer nodes but needs larger frontier,
    while DFS keeps small frontier but may need to expand more nodes.
    
    Args:
        bfs_logs: List of BFS log entries.
        dfs_logs: List of DFS log entries.
        output_file: Output PNG file path.
        title: Chart title.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Extract data
    bfs_expanded = [log["expanded_nodes"] for log in bfs_logs]
    bfs_frontiers = [log["frontier_size"] for log in bfs_logs]
    
    dfs_expanded = [log["expanded_nodes"] for log in dfs_logs]
    dfs_frontiers = [log["frontier_size"] for log in dfs_logs]
    
    # Scatter plots with different sizes/colors
    ax.scatter(bfs_expanded, bfs_frontiers, s=100, alpha=0.6, label='BFS',
               color='#1f77b4', edgecolors='black', linewidth=0.5)
    ax.scatter(dfs_expanded, dfs_frontiers, s=100, alpha=0.6, label='DFS',
               color='#ff7f0e', edgecolors='black', linewidth=0.5)
    
    # Formatting
    ax.set_xlabel('Nodes Expanded', fontsize=12, fontweight='bold')
    ax.set_ylabel('Frontier Size', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold')
    
    # Grid
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=11, loc='best')
    
    # Format axes with commas
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f'{int(x):,}'))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f'{int(x):,}'))
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    print(f"✓ Chart 3 saved: {output_file}")
    plt.close()


def generate_all_charts(
    input_dir: str,
    output_dir: str,
    deal: int = 42
):
    """Generate all 3 charts for a single deal.
    
    Args:
        input_dir: Directory containing JSON log files.
        output_dir: Directory to save PNG charts.
        deal: Deal number.
    """
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    # Load logs
    bfs_file = f"{input_dir}/bfs_deal{deal}.json"
    dfs_file = f"{input_dir}/dfs_deal{deal}.json"
    
    print(f"\nLoading logs for deal #{deal}...")
    print(f"  BFS: {bfs_file}")
    print(f"  DFS: {dfs_file}")
    
    bfs_data = load_logs(bfs_file)
    dfs_data = load_logs(dfs_file)
    
    bfs_logs = bfs_data["logs"]
    dfs_logs = dfs_data["logs"]
    
    print(f"  BFS logs: {len(bfs_logs)} entries")
    print(f"  DFS logs: {len(dfs_logs)} entries")
    
    # Generate charts
    print(f"\nGenerating charts...")
    
    chart1_file = f"{output_dir}/01_frontier_growth_deal{deal}.png"
    plot_frontier_growth(bfs_logs, dfs_logs, chart1_file)
    
    chart2_file = f"{output_dir}/02_expanded_nodes_vs_time_deal{deal}.png"
    plot_expanded_nodes_vs_time(bfs_logs, dfs_logs, chart2_file)
    
    chart3_file = f"{output_dir}/03_efficiency_tradeoff_deal{deal}.png"
    plot_efficiency_tradeoff(bfs_logs, dfs_logs, chart3_file)
    
    print(f"\n✓ All charts generated in {output_dir}/")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate visualization charts from experiment logs"
    )
    parser.add_argument("--input-dir", default="experiment_logs", help="Input logs directory")
    parser.add_argument("--output-dir", default="plots", help="Output plots directory")
    parser.add_argument("--deal", type=int, default=42, help="Deal number to visualize")
    parser.add_argument("--all-deals", action="store_true", help="Generate charts for deals 42, 43, 44")
    
    args = parser.parse_args()
    
    if args.all_deals:
        # Generate for all deals
        for deal in [42, 43, 44]:
            try:
                generate_all_charts(args.input_dir, args.output_dir, deal)
            except FileNotFoundError as e:
                print(f"⚠ Deal #{deal}: {e}")
    else:
        # Single deal
        generate_all_charts(args.input_dir, args.output_dir, args.deal)


if __name__ == "__main__":
    main()
