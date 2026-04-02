# Controlled Experiment Framework for BFS vs DFS

## Overview

This framework enables fair, controlled comparison of BFS and DFS algorithms on FreeCell. Unlike full solver runs, these experiments **stop early** based on configurable limits to collect clean data for visualization.

**Key Feature**: Both algorithms run on the **same initial state** with **identical stopping conditions**.

---

## Architecture

### 1. Experiment Classes

#### `BFSExperiment` (`backend/search/bfs_experiment.py`)
- FIFO frontier-based BFS with early stopping
- Logs metrics at regular intervals
- Stops due to:
  - `max_frontier_size`: Frontier exceeds Size (e.g., 50,000)
  - `max_expanded_nodes`: Total expansions exceed limit (e.g., 100,000)
  - `max_time_seconds`: Elapsed time exceeds limit (e.g., 30s)
  - `goal_found`: Solution discovered (rare in experiment mode)

#### `DFSExperiment` (`backend/search/dfs_experiment.py`)
- LIFO stack-based DFS with global visited set
- Same early stopping conditions as BFS
- Logs identical metrics for fair comparison

### 2. Fair Experiment Runner

**File**: `run_experiment.py`

Runs both BFS and DFS on the same initial state with identical limits.

**Key Features**:
- Single deal or multiple deals (42, 43, 44)
- Configurable limits
- Outputs JSON logs for each algorithm
- Generates summary file

### 3. Visualization Script

**File**: `plot_experiment.py`

Generates 3 required charts using **matplotlib only** (no seaborn):

1. **Frontier Growth** - Time vs Frontier Size (log Y-axis)
2. **Nodes Expanded** - Time vs Expanded Nodes
3. **Efficiency Trade-off** - Scatter plot (Nodes vs Frontier)

---

## Quick Start

### Step 1: Run Experiments

#### Single Deal
```bash
python run_experiment.py --deal 42 \
    --max-frontier 50000 \
    --max-nodes 100000 \
    --max-time 30
```

#### Multiple Deals (42, 43, 44)
```bash
python run_experiment.py --multi-deal \
    --max-frontier 50000 \
    --max-nodes 100000 \
    --max-time 30
```

#### Command-line Options
| Option | Default | Description |
|--------|---------|-------------|
| `--deal` | 42 | Deal number |
| `--max-frontier` | 50,000 | Max frontier/stack size |
| `--max-nodes` | 100,000 | Max nodes to expand |
| `--max-time` | 30.0 | Max time in seconds |
| `--log-interval` | 100 | Log every N expansions |
| `--output-dir` | experiment_logs | Output directory |
| `--multi-deal` | - | Run deals 42, 43, 44 |

### Step 2: Generate Visualizations

```bash
python plot_experiment.py \
    --input-dir experiment_logs \
    --output-dir plots \
    --deal 42
```

Or for all deals:
```bash
python plot_experiment.py --all-deals
```

---

## Output Format

### Log Files

Each run produces:
- `experiment_logs/bfs_deal{N}.json` - BFS detailed logs
- `experiment_logs/dfs_deal{N}.json` - DFS detailed logs
- `experiment_logs/summary_deal{N}.json` - Summary statistics

### Log Entry Structure

```json
{
  "algorithm": "BFS",
  "step": 0,
  "time": 0.1234,
  "frontier_size": 1250,
  "expanded_nodes": 1000,
  "current_depth": 8
}
```

### Summary Structure

```json
{
  "deal": 42,
  "parameters": {...},
  "bfs": {
    "stop_reason": "max_frontier_size_exceeded",
    "elapsed_time": 25.43,
    "solution_found": false,
    "solution_length": -1,
    "total_nodes_expanded": 50000,
    "final_frontier_size": 50001,
    "log_file": "experiment_logs/bfs_deal42.json"
  },
  "dfs": {...}
}
```

---

## Visualization Output

### Chart 1: Frontier Growth
- **File**: `01_frontier_growth_deal{N}.png`
- **X-axis**: Time (seconds)
- **Y-axis**: Frontier Size (log scale)
- **Key Insight**: Shows exponential growth of BFS frontier vs bounded DFS stack

### Chart 2: Nodes Expanded vs Time
- **File**: `02_expanded_nodes_vs_time_deal{N}.png`
- **X-axis**: Time (seconds)
- **Y-axis**: Nodes Expanded (linear)
- **Key Insight**: Shows exploration speed of each algorithm

### Chart 3: Efficiency Trade-off
- **File**: `03_efficiency_tradeoff_deal{N}.png`
- **X-axis**: Nodes Expanded
- **Y-axis**: Frontier Size
- **Type**: Scatter plot
- **Key Insight**: Shows BFS expands fewer nodes but uses more memory; DFS inverse

---

## How to Interpret Results

### BFS Typical Behavior
- **Frontier Growth**: Exponential → hits limit quickly
- **Nodes Expanded**: Steady increase until frontier limit
- **Time**: Longer (more iterations at higher frontier sizes)
- **Solution**: IF found, guaranteed optimal (shortest path)

### DFS Typical Behavior
- **Frontier Growth**: Small, bounded stack
- **Nodes Expanded**: Can reach limit faster (fewer memory constraints)
- **Time**: Often shorter (first-found solution)
- **Solution**: NOT optimal (may be 2-10x longer than BFS)

### Trade-off
- **BFS**: Memory bottleneck (frontier)
- **DFS**: Time bottleneck (explores more nodes to reach goal)

---

## Advanced Configuration

### Running with Different Limits

For memory-focused study:
```bash
python run_experiment.py --max-frontier 10000 --max-nodes 1000000
```

For time-focused study:
```bash
python run_experiment.py --max-frontier 100000 --max-time 5
```

### Log Interval Tuning

- `--log-interval 1` → Log every expansion (very detailed, slower)
- `--log-interval 100` → Log every 100 expansions (balanced)
- `--log-interval 1000` → Log every 1000 expansions (sparse)

---

## Implementation Details

### Why Early Stopping?

Full FreeCell solving would require:
- Hour(s) of computation per deal
- Production-level optimization
- Complex heuristics

Instead, experiments:
- Stop within seconds
- Collect clean growth data
- Show algorithm behavior under pressure

### Metrics Collection

**Not optimized away**:
- Visited set maintained (prevents cycles)
- Frontier logged at each interval
- Parent pointers tracked (allows path reconstruction)

**Key metric**: Frontier size shows memory pressure

### Python Implementation Notes

- `collections.deque` for BFS: O(1) amortized append/popleft
- `list.pop()` for DFS: O(1) amortized
- `set` for visited hashing: O(1) average lookup
- `dict` for parent pointers: O(1) lookup

---

## Troubleshooting

### "No logs generated"
- Check `--log-interval` is not too large
- Verify stop reason in summary (may have stopped immediately)

### Frontier doesn't grow
- May indicate unfavorable move ordering for BFS
- Try different `--deal` number

### High memory usage
- Normal for BFS with large max_frontier
- Reduce `--max-frontier` if needed

---

## Example Workflow

```bash
# 1. Run single deal
python run_experiment.py --deal 42

# 2. Generate charts
python plot_experiment.py --deal 42

# 3. View results in plots/ directory
open plots/01_frontier_growth_deal42.png

# 4. Compare multiple limits
python run_experiment.py --deal 42 --max-frontier 10000
python run_experiment.py --deal 42 --max-frontier 30000
python run_experiment.py --deal 42 --max-frontier 50000

# 5. Generate multi-deal comparison
python run_experiment.py --multi-deal --max-frontier 50000
python plot_experiment.py --all-deals
```

---

## Performance Notes

**Typical run times** (Intel i7, Python 3.10):
- Single deal: 30-60 seconds
- Three deals: 2-3 minutes
- Visualization: <5 seconds per deal

---

## Future Extensions

Possible enhancements:
- Memory tracking via `tracemalloc`
- Branching factor estimation
- Depth distribution histograms
- Heuristic-guided search comparison (A*, UCS)

---

## Summary

This framework provides:
✓ Fair BFS vs DFS comparison  
✓ Controlled early stopping  
✓ Clean data collection  
✓ 3-chart visualization  
✓ JSON output for further analysis  

Use it to study algorithm behavior, not to win games!
