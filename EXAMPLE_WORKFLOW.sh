#!/bin/bash
# Example Experiment Workflow
# This file shows all the commands needed to:
# 1. Run experiments with different configurations
# 2. Generate visualizations
# 3. Analyze results

# ============================================================
# PART 1: SINGLE DEAL TEST
# ============================================================

echo "=== PART 1: Single Deal Test ==="
echo "Running Deal #42 with default limits..."

python run_experiment.py --deal 42

echo "Generating charts..."
python plot_experiment.py --deal 42

echo "Results available in:"
echo "  - experiment_logs/bfs_deal42.json"
echo "  - experiment_logs/dfs_deal42.json"
echo "  - experiment_logs/summary_deal42.json"
echo "  - plots/01_frontier_growth_deal42.png"
echo "  - plots/02_expanded_nodes_vs_time_deal42.png"
echo "  - plots/03_efficiency_tradeoff_deal42.png"

# ============================================================
# PART 2: BATCH PROCESSING (Multiple Deals)
# ============================================================

echo ""
echo "=== PART 2: Batch Processing ==="
echo "Running all three test deals (42, 43, 44)..."

python run_experiment.py --multi-deal

echo "Generating batch visualizations..."
python plot_experiment.py --all-deals

# ============================================================
# PART 3: COMPARATIVE STUDY (Different Limits)
# ============================================================

echo ""
echo "=== PART 3: Comparative Study ==="
echo "Running Deal #42 with DIFFERENT FRONTIER LIMITS..."
echo "This lets you see how both algorithms scale..."

# Test with 3 different frontier limits
for LIMIT in 10000 30000 50000; do
    echo ""
    echo "Running with max-frontier=$LIMIT..."
    python run_experiment.py --deal 42 \
        --max-frontier $LIMIT \
        --max-time 20 \
        --output-dir experiment_logs_limit_${LIMIT}
done

echo ""
echo "Results saved in:"
echo "  - experiment_logs_limit_10000/"
echo "  - experiment_logs_limit_30000/"
echo "  - experiment_logs_limit_50000/"

# ============================================================
# PART 4: ANALYZE RESULTS
# ============================================================

echo ""
echo "=== PART 4: Analyze Summary Statistics ==="
echo "Quick look at results..."

# On Linux/Mac, use 'cat' or 'jq' for JSON
# On Windows PowerShell, use 'Get-Content' or 'ConvertFrom-Json'

echo ""
echo "BFS vs DFS Summary:"
cat experiment_logs/summary_deal42.json

# ============================================================
# PART 5: CUSTOM EXPERIMENT
# ============================================================

echo ""
echo "=== PART 5: Custom Experiment ==="
echo "You can customize ALL parameters..."

python run_experiment.py \
    --deal 43 \
    --max-frontier 100000 \
    --max-nodes 500000 \
    --max-time 60 \
    --log-interval 500 \
    --output-dir experiment_logs_custom

echo "Custom results in experiment_logs_custom/"

# ============================================================
# SUMMARY
# ============================================================

echo ""
echo "========================================"
echo "EXPERIMENT FRAMEWORK WORKFLOWS COMPLETE"
echo "========================================"
echo ""
echo "Key outputs:"
echo "  1. JSON logs for further analysis"
echo "  2. PNG charts for reports"
echo "  3. Summary statistics"
echo ""
echo "Next steps:"
echo "  - Open plots/*.png in image viewer"
echo "  - View experiment_logs/summary*.json for stats"
echo "  - Use data in your report"
echo ""
echo "For help, see:"
echo "  - QUICK_REFERENCE.md (fast lookup)"
echo "  - EXPERIMENT_GUIDE.md (full details)"
echo ""
