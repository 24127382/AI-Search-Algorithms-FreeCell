"""Quick experiment run with reduced search limits for fast results."""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.experiments.runner import ExperimentRunner, create_initial_state
from backend.search.bfs import BFSAlgorithm
from backend.search.dfs import DFSAlgorithm
from backend.model.state import State

def run_quick_experiments(num_deals: int = 3, max_nodes: int = 50000):
    """Run quick experiments with limited search scope."""
    results = []
    
    print(f"Running quick experiments on {num_deals} deals (max {max_nodes} nodes per search)...")
    
    for deal_idx in range(num_deals):
        deal_number = 42 + deal_idx  # Use deals 42, 43, 44
        print(f"\n[Deal {deal_idx + 1}/{num_deals}] Generating state...", flush=True, end=" ")
        
        try:
            state = create_initial_state(deal_number)
            print(f"OK ({len(state.tableau)} columns)")
            
            # Run BFS
            print(f"  BFS (max {max_nodes} nodes)...", flush=True, end=" ")
            bfs = BFSAlgorithm(state, collect_metrics=True, max_nodes=max_nodes)
            bfs_solution = bfs.search()
            bfs_metrics = bfs.get_metrics()
            if bfs_metrics:
                bfs_dict = bfs_metrics.to_dict()
                bfs_dict["deal_id"] = deal_idx
                results.append(bfs_dict)
                status = f"OK ({bfs_metrics.expanded_nodes} nodes, {bfs_metrics.time_seconds:.2f}s)"
                if bfs_metrics.solution_length > 0:
                    status += f", {bfs_metrics.solution_length} moves"
                else:
                    status += " [NO SOLUTION FOUND]"
                print(status)
            else:
                print("FAILED (no metrics)")
            
            # Run DFS
            print(f"  DFS (max {max_nodes} nodes)...", flush=True, end=" ")
            dfs = DFSAlgorithm(state, collect_metrics=True, max_nodes=max_nodes)
            dfs_solution = dfs.search()
            dfs_metrics = dfs.get_metrics()
            if dfs_metrics:
                dfs_dict = dfs_metrics.to_dict()
                dfs_dict["deal_id"] = deal_idx
                results.append(dfs_dict)
                status = f"OK ({dfs_metrics.expanded_nodes} nodes, {dfs_metrics.time_seconds:.2f}s)"
                if dfs_metrics.solution_length > 0:
                    status += f", {dfs_metrics.solution_length} moves"
                else:
                    status += " [NO SOLUTION FOUND]"
                print(status)
            else:
                print("FAILED (no metrics)")
                
        except Exception as e:
            print(f"ERROR: {e}")
    
    # Save results
    output_file = "results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Results saved to {output_file}")
    
    # Print summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    for r in results:
        status = "✓" if r["solution_length"] > 0 else "✗"
        print(f"{status} Deal {r['deal_id']+1} {r['algorithm']}: {r['expanded_nodes']} nodes, {r['time_seconds']:.2f}s")

if __name__ == "__main__":
    # Run with reduced limits
    run_quick_experiments(num_deals=3, max_nodes=50000)
