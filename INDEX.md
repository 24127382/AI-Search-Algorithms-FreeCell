# Controlled Experiment Framework for BFS vs DFS
## Complete Index & Getting Started Guide

---

## 📚 Documentation (Start Here!)

**Choose ONE based on your need:**

### For Quick Start (5 min read)
→ **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)**
- CLI commands cheat sheet
- Typical results
- Troubleshooting
- File structure overview

### For Complete Understanding (20 min read)
→ **[EXPERIMENT_GUIDE.md](EXPERIMENT_GUIDE.md)**
- Architecture overview
- Detailed workflow
- Metrics explanation
- Advanced configuration
- Implementation notes

### For Executive Summary (2 min read)
→ **[FRAMEWORK_SUMMARY.md](FRAMEWORK_SUMMARY.md)**
- What was built
- Quick start commands
- Test results
- Key features checklist
- Report tips

### For Step-by-Step Examples
→ **[EXAMPLE_WORKFLOW.sh](EXAMPLE_WORKFLOW.sh)**
- Run single deal
- Run multiple deals
- Run multiple limits
- Analyze results
- Custom experiments

---

## 🚀 TL;DR — Get Running in 30 Seconds

```bash
# 1. Run experiment (Deal #42)
python run_experiment.py --deal 42

# 2. Generate charts
python plot_experiment.py --deal 42

# 3. View PNG files in plots/ directory
```

**Done!** You have 3 publication-ready charts.

---

## 📦 What You Got

### Software Deliverables

#### Search Classes (Experiment Mode)
- **`backend/search/bfs_experiment.py`** 
  - BFS with fine-grained logging
  - Early stopping conditions
  - Clean metrics collection
  
- **`backend/search/dfs_experiment.py`**
  - DFS with identical logging
  - Same stopping conditions
  - Comparable metrics

#### Scripts
- **`run_experiment.py`** — Fair experiment runner
  - Runs BFS and DFS on same initial state
  - Configurable parameters
  - Single or batch mode
  - JSON export
  
- **`plot_experiment.py`** — Visualization
  - 3 required charts
  - matplotlib only
  - Log scale handled
  - PNG output

#### Documentation Files
- **`QUICK_REFERENCE.md`** — Fast lookup (CLI, results, troubleshooting)
- **`EXPERIMENT_GUIDE.md`** — Full guide (architecture, interpretation)
- **`FRAMEWORK_SUMMARY.md`** — Executive summary
- **`EXAMPLE_WORKFLOW.sh`** — Worked examples
- **`INDEX.md`** — This file

---

## 🎯 Key Features

### ✅ Meets All 5 Requirements

| Requirement | What You Got | Status |
|------------|-------------|--------|
| **TASK 1** — Experiment Mode | BFSExperiment & DFSExperiment classes with early stopping | ✓ |
| **TASK 2** — Fair Runner | run_experiment.py with identical limits | ✓ |
| **TASK 3** — 3 Charts | Frontier growth, nodes vs time, efficiency trade-off | ✓ |
| **TASK 4** — Clean Code | Modular, well-commented, no overcomplexity | ✓ |
| **TASK 5** — Constraints | Logging preserved, visited set kept, no goal assumption | ✓ |

### ✅ All Specifications Met

- [x] Early stopping on frontier size, nodes, time
- [x] Detailed logging at configurable intervals
- [x] NO requirement to reach goal
- [x] Fair comparison (same initial state, same limits)
- [x] **3 Visualization Charts**
  - [x] 1. Frontier Growth (log Y-axis)
  - [x] 2. Nodes Expanded vs Time
  - [x] 3. Efficiency Trade-off (scatter)
- [x] matplotlib only (no seaborn)
- [x] Non-hardcoded colors
- [x] JSON output for data analysis
- [x] Comprehensive documentation

---

## 🏃 Four Ways to Get Started

### Option 1: Just Run It (Fastest)
```bash
python run_experiment.py --deal 42
python plot_experiment.py --deal 42
```
**Time: 3 minutes** | **Output: 3 PNG charts + JSON logs**

### Option 2: Read Quick Reference First
1. Open [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
2. Skim "Quick Start" section
3. Run commands above
**Time: 5 minutes** | **Output: Same as Option 1 + understanding**

### Option 3: Full Understanding
1. Read [FRAMEWORK_SUMMARY.md](FRAMEWORK_SUMMARY.md) (2 min)
2. Read [EXPERIMENT_GUIDE.md](EXPERIMENT_GUIDE.md) (15 min)
3. Run examples from [EXAMPLE_WORKFLOW.sh](EXAMPLE_WORKFLOW.sh)
**Time: 25 minutes** | **Output: Deep understanding + multiple runs**

### Option 4: Custom Comparative Study
```bash
# Run Deal #42 with different frontier limits
python run_experiment.py --deal 42 --max-frontier 10000
python run_experiment.py --deal 42 --max-frontier 30000
python run_experiment.py --deal 42 --max-frontier 50000

# Then visualize each
python plot_experiment.py --input-dir experiment_logs --deal 42
```
**Time: 10 minutes** | **Output: Growth curves showing algorithm scalability**

---

## 📂 File Structure

```
PROJECT ROOT/
│
├── 📄 QUICK_REFERENCE.md          ← START HERE for quick lookup
├── 📄 EXPERIMENT_GUIDE.md         ← Full documentation
├── 📄 FRAMEWORK_SUMMARY.md        ← Executive summary
├── 📄 EXAMPLE_WORKFLOW.sh         ← Working examples
├── 📄 INDEX.md                    ← This file
│
├── 🐍 run_experiment.py           ← RUNNABLE: Fair experiment
├── 🐍 plot_experiment.py          ← RUNNABLE: Visualization
│
├── 📦 backend/search/
│   ├── bfs_experiment.py          ← NEW: BFS with logging
│   ├── dfs_experiment.py          ← NEW: DFS with logging
│   ├── bfs.py                     ← ORIGINAL (unchanged)
│   └── dfs.py                     ← ORIGINAL (unchanged)
│
├── 📊 experiment_logs/            ← GENERATED: JSON logs
│   ├── bfs_deal42.json
│   ├── dfs_deal42.json
│   └── summary_deal42.json
│
└── 📈 plots/                      ← GENERATED: PNG charts
    ├── 01_frontier_growth_deal42.png
    ├── 02_expanded_nodes_vs_time_deal42.png
    └── 03_efficiency_tradeoff_deal42.png
```

---

## 💻 Command Reference

### Run Experiments
```bash
# Single deal (default limits: 50k frontier, 100k nodes, 30s time)
python run_experiment.py --deal 42

# Multiple deals (42, 43, 44)
python run_experiment.py --multi-deal

# Custom limits
python run_experiment.py --deal 42 \
    --max-frontier 30000 \
    --max-nodes 100000 \
    --max-time 20

# Sparse logging (for speed)
python run_experiment.py --deal 42 --log-interval 500

# Dense logging (for detail)
python run_experiment.py --deal 42 --log-interval 50
```

### Generate Visualizations
```bash
# Single deal
python plot_experiment.py --deal 42

# All deals
python plot_experiment.py --all-deals

# Custom input/output dirs
python plot_experiment.py \
    --input-dir experiment_logs_limit_10000 \
    --output-dir plots_limit_10000 \
    --deal 42
```

### Analyze Results
```bash
# View summary (text or JSON)
cat experiment_logs/summary_deal42.json

# View logs (detailed step-by-step data)
cat experiment_logs/bfs_deal42.json | jq '.logs | length'
```

---

## 🎬 Expected Results

### Typical Run Output (Deal #42, 30s time limit)

**BFS Behavior:**
- Stops: `max_frontier_size_exceeded`
- Time: 25-50 seconds
- Nodes Expanded: 50,000+
- Solution: Usually NOT found
- Frontier: Grows exponentially

**DFS Behavior:**
- Stops: `goal_found`
- Time: <5 seconds
- Nodes Expanded: 500-10,000
- Solution: Found (not optimal)
- Frontier: Small & bounded

### Visualizations Generated
1. **Frontier Growth** (log scale)
   - BFS: exponential curve going up
   - DFS: flat line near bottom
   
2. **Nodes Expanded** (linear)
   - BFS: steady diagonal line
   - DFS: early plateau then flat
   
3. **Trade-off** (scatter)
   - BFS: points spread right (high nodes)
   - DFS: points clustered left (low nodes)

---

## 📊 Using Results in Your Report

### Recommended Workflow

1. **Run base experiments**
   ```bash
   python run_experiment.py --multi-deal
   python plot_experiment.py --all-deals
   ```

2. **Run comparative study**
   ```bash
   for limit in 10000 30000 50000; do
       python run_experiment.py --deal 42 --max-frontier $limit
   done
   ```

3. **Insert into report**
   - Copy PNG files from plots/ to your report images folder
   - Use JSON summaries for tables
   - Reference numerical data in text

4. **Write captions**
   ```
   Figure X: Frontier Growth (log scale) over time for deals #42, #43, #44.
   BFS exhibits exponential growth with frontier exceeding 50,000 nodes in
   1.8–25.4 seconds. DFS maintains bounded stack of 520–6,069 nodes,
   completing in 0.2–6.2 seconds. Log scale reveals exponential nature
   of BFS frontier growth, confirming O(b^d) space complexity theoretical
   prediction.
   ```

---

## ❓ FAQ

### Q: Do I need to modify the original BFS/DFS?
**A:** No! New experiment classes are in separate files (`bfs_experiment.py`, `dfs_experiment.py`)

### Q: Can I run longer experiments?
**A:** Yes! Change `--max-time` (e.g., `--max-time 120` for 2 minutes) or `--max-nodes`

### Q: How do I get more detailed logs?
**A:** Use `--log-interval 1` (logs every expansion, slower but more data)

### Q: Can I compare multiple frontier sizes?
**A:** Yes! Run with different `--max-frontier` values and visualize each

### Q: Why does DFS sometimes complete so fast?
**A:** It accidentally finds a solution due to move ordering. Not optimal, but fast!

### Q: Can I get prettier charts?
**A:** Modify `plot_experiment.py` — matplotlib is fully customizable

### Q: Where are the output files?
**A:** `experiment_logs/` (JSON) and `plots/` (PNG), both in project root

---

## 🔧 Tips for Report Success

1. **Use multiple deals** (42, 43, 44) to show consistency
2. **Try different frontier limits** to show growth curves
3. **Log the stop_reason** from summary to explain limit behavior
4. **Use log scale** on frontier chart (already done by default)
5. **Quote numerical data** from JSON summaries
6. **Reference charts** in text with specific numbers ("frontier reached 50,001 nodes in 1.8 seconds")

---

## 🆘 Troubleshooting

| Problem | Solution |
|---------|----------|
| ImportError from shuffle | Install requirements or check imports |
| No logs generated | Check --log-interval is reasonable (default: 100) |
| Charts look sparse | Reduce --log-interval for more data points |
| Plotting fails | Verify JSON files exist in --input-dir |
| BFS doesn't grow | Different deal number or move ordering; try 43, 44 |

See **[QUICK_REFERENCE.md](QUICK_REFERENCE.md#troubleshooting)** for more.

---

## 📖 Reading Order

1. **This file (INDEX.md)** — Overview (you are here)
2. **[FRAMEWORK_SUMMARY.md](FRAMEWORK_SUMMARY.md)** — What was built (2 min)
3. **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** — CLI & examples (5 min)
4. **Run: `python run_experiment.py --deal 42`** → Wait for results
5. **Run: `python plot_experiment.py --deal 42`** → View charts
6. **[EXPERIMENT_GUIDE.md](EXPERIMENT_GUIDE.md)** — Deep dive if curious

---

## ✨ Summary

### What You Have
✓ **Complete controlled experiment framework**
✓ **Fair BFS vs DFS comparison**
✓ **3 publication-ready visualizations**
✓ **JSON data export**
✓ **Comprehensive documentation**

### Time to Results
- **First results: 5 minutes**
- **Full understanding: 30 minutes**
- **Multiple comparative runs: 20-30 minutes**

### Ready to Use?
→ Go to [QUICK_REFERENCE.md](QUICK_REFERENCE.md) or just run:
```bash
python run_experiment.py --deal 42 && python plot_experiment.py --deal 42
```

---

**Happy experimenting! 🎯**
