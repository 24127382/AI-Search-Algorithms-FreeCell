"""Quick test to verify visualization works with synthetic data."""
import json
import random
from visualization import ExperimentVisualizer

# Generate synthetic results matching the expected format
# Expected format: flat list where each result has algorithm, deal_id, times, nodes, etc.
results = []

# Create 5 deals with synthetic data
for deal_num in range(1, 6):
    bfs_nodes = random.randint(1000, 50000)
    dfs_nodes = random.randint(500, 30000)
    bfs_time = bfs_nodes / 5000 + random.uniform(0.1, 1.5)  # ~5k nodes/sec
    dfs_time = dfs_nodes / 3000 + random.uniform(0.1, 1.5)  # ~3k nodes/sec
    
    # BFS result
    results.append({
        "algorithm": "BFS",
        "deal_id": deal_num,
        "time_seconds": round(bfs_time, 2),
        "peak_memory_mb": round(random.uniform(20, 150), 1),
        "expanded_nodes": bfs_nodes,
        "solution_length": random.randint(30, 100),
        "frontier_max_size": random.randint(100, 5000)
    })
    
    # DFS result
    results.append({
        "algorithm": "DFS",
        "deal_id": deal_num,
        "time_seconds": round(dfs_time, 2),
        "peak_memory_mb": round(random.uniform(15, 120), 1),
        "expanded_nodes": dfs_nodes,
        "solution_length": random.randint(50, 200),
        "frontier_max_size": random.randint(50, 3000)
    })

# Save and visualize
output_file = "results_demo.json"
with open(output_file, "w") as f:
    json.dump(results, f, indent=2)

print(f"✓ Generated synthetic results: {output_file}")

# Test visualization
print("\nGenerating visualization plots...")
visualizer = ExperimentVisualizer(output_file)

plots = [
    ("nodes_vs_time.png", visualizer.plot_nodes_vs_time),
    ("memory_comparison.png", visualizer.plot_memory_comparison),
    ("solution_length_comparison.png", visualizer.plot_solution_length_comparison),
    ("frontier_size_comparison.png", visualizer.plot_frontier_size_comparison),
]

for filename, plot_func in plots:
    try:
        plot_func(filename)
        print(f"  ✓ {filename}")
    except Exception as e:
        print(f"  ✗ {filename}: {e}")

print("\n✓ Visualization test complete!")
print("\nSample data:")
visualizer.print_summary_table()
