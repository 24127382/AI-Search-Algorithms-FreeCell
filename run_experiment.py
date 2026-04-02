#!/usr/bin/env python3
"""Fair comparison experiment runner for BFS vs DFS.

This script runs both BFS and DFS on the same initial state with identical stopping limits.
Results are saved to JSON files for visualization.

Usage:
    python run_experiment.py --deal 42 --max-frontier 50000 --max-nodes 100000 --max-time 30
"""

import json
import time
import argparse
from pathlib import Path

from backend.engine.shuffle import deal_by_game_number
from backend.model.state import State
from backend.search.bfs_experiment import BFSExperiment
from backend.search.dfs_experiment import DFSExperiment


def get_initial_state(deal: int) -> State:
    """Generate initial state for a given deal number.
    
    Args:
        deal: Deal number (FreeCell game number).
    
    Returns:
        State: Initial game state.
    """
    tableau = deal_by_game_number(deal)
    # Initialize freecells (empty) and foundations (empty)
    freecells = [None, None, None, None]
    foundations = [[], [], [], []]
    
    return State(
        tableau=tuple(tuple(col) for col in tableau),
        freecells=tuple(freecells),
        foundations=tuple(tuple(f) for f in foundations)
    )


def run_experiments(
    deal: int,
    max_frontier: int = 50000,
    max_expanded: int = 100000,
    max_time: float = 30.0,
    log_interval: int = 100,
    output_dir: str = "experiment_logs"
) -> dict:
    """Run BFS and DFS on the same state with identical limits.
    
    Args:
        deal: Deal number.
        max_frontier: Maximum frontier/stack size.
        max_expanded: Maximum nodes to expand.
        max_time: Maximum time in seconds.
        log_interval: Log every N expansions.
        output_dir: Directory to save JSON logs.
    
    Returns:
        dict: Summary of experiment results.
    """
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    # Get initial state
    print(f"\n{'='*60}")
    print(f"DEAL #{deal}")
    print(f"{'='*60}")
    print(f"Max frontier: {max_frontier:,}")
    print(f"Max nodes: {max_expanded:,}")
    print(f"Max time: {max_time}s")
    print(f"Log interval: {log_interval}")
    
    initial_state = get_initial_state(deal)
    print(f"Initial state generated.")
    
    # --- RUN BFS ---
    print(f"\n[BFS] Starting...")
    bfs_start = time.time()
    bfs = BFSExperiment(
        initial_state,
        max_frontier_size=max_frontier,
        max_expanded_nodes=max_expanded,
        max_time_seconds=max_time,
        log_interval=log_interval
    )
    bfs_solution = bfs.search()
    bfs_time = time.time() - bfs_start
    
    print(f"[BFS] Stopped: {bfs.stop_reason}")
    print(f"[BFS] Time: {bfs_time:.2f}s")
    print(f"[BFS] Logs collected: {len(bfs.logs)}")
    if bfs.logs:
        print(f"      Final frontier: {bfs.logs[-1]['frontier_size']:,}")
        print(f"      Final expanded: {bfs.logs[-1]['expanded_nodes']:,}")
    
    bfs_log_file = f"{output_dir}/bfs_deal{deal}.json"
    bfs.save_logs(bfs_log_file)
    
    # --- RUN DFS ---
    print(f"\n[DFS] Starting...")
    dfs_start = time.time()
    dfs = DFSExperiment(
        initial_state,
        max_frontier_size=max_frontier,
        max_expanded_nodes=max_expanded,
        max_time_seconds=max_time,
        log_interval=log_interval
    )
    dfs_solution = dfs.search()
    dfs_time = time.time() - dfs_start
    
    print(f"[DFS] Stopped: {dfs.stop_reason}")
    print(f"[DFS] Time: {dfs_time:.2f}s")
    print(f"[DFS] Logs collected: {len(dfs.logs)}")
    if dfs.logs:
        print(f"      Final frontier: {dfs.logs[-1]['frontier_size']:,}")
        print(f"      Final expanded: {dfs.logs[-1]['expanded_nodes']:,}")
    
    dfs_log_file = f"{output_dir}/dfs_deal{deal}.json"
    dfs.save_logs(dfs_log_file)
    
    # --- SUMMARY ---
    summary = {
        "deal": deal,
        "parameters": {
            "max_frontier": max_frontier,
            "max_expanded_nodes": max_expanded,
            "max_time_seconds": max_time,
            "log_interval": log_interval
        },
        "bfs": {
            "stop_reason": bfs.stop_reason,
            "elapsed_time": round(bfs_time, 4),
            "solution_found": bfs_solution is not None,
            "solution_length": len(bfs_solution) if bfs_solution else -1,
            "total_nodes_expanded": bfs.logs[-1]["expanded_nodes"] if bfs.logs else 0,
            "final_frontier_size": bfs.logs[-1]["frontier_size"] if bfs.logs else 0,
            "log_file": bfs_log_file
        },
        "dfs": {
            "stop_reason": dfs.stop_reason,
            "elapsed_time": round(dfs_time, 4),
            "solution_found": dfs_solution is not None,
            "solution_length": len(dfs_solution) if dfs_solution else -1,
            "total_nodes_expanded": dfs.logs[-1]["expanded_nodes"] if dfs.logs else 0,
            "final_frontier_size": dfs.logs[-1]["frontier_size"] if dfs.logs else 0,
            "log_file": dfs_log_file
        }
    }
    
    # Save summary
    summary_file = f"{output_dir}/summary_deal{deal}.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n[SUMMARY] Saved to {summary_file}")
    print(f"\n{'='*60}")
    
    return summary


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fair comparison experiment: BFS vs DFS on FreeCell"
    )
    parser.add_argument("--deal", type=int, default=42, help="Deal number (default: 42)")
    parser.add_argument("--max-frontier", type=int, default=50000, help="Max frontier size")
    parser.add_argument("--max-nodes", type=int, default=100000, help="Max expanded nodes")
    parser.add_argument("--max-time", type=float, default=30.0, help="Max time in seconds")
    parser.add_argument("--log-interval", type=int, default=100, help="Log every N expansions")
    parser.add_argument("--output-dir", default="experiment_logs", help="Output directory")
    parser.add_argument("--multi-deal", action="store_true", help="Run on deals 42, 43, 44")
    
    args = parser.parse_args()
    
    if args.multi_deal:
        # Run on multiple deals
        all_summaries = []
        for deal in [42, 43, 44]:
            summary = run_experiments(
                deal=deal,
                max_frontier=args.max_frontier,
                max_expanded=args.max_nodes,
                max_time=args.max_time,
                log_interval=args.log_interval,
                output_dir=args.output_dir
            )
            all_summaries.append(summary)
        
        # Save overall summary
        overall_file = f"{args.output_dir}/overall_summary.json"
        with open(overall_file, 'w') as f:
            json.dump(all_summaries, f, indent=2)
        print(f"\n[OVERALL] Results saved to {overall_file}")
    else:
        # Single deal
        run_experiments(
            deal=args.deal,
            max_frontier=args.max_frontier,
            max_expanded=args.max_nodes,
            max_time=args.max_time,
            log_interval=args.log_interval,
            output_dir=args.output_dir
        )


if __name__ == "__main__":
    main()
