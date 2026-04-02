#!/usr/bin/env python3
"""Benchmark runner: Zobrist hashing vs. Bit-Packing comparison.

Runs controlled experiments on Microsoft FreeCell standard deals.

Usage:
    python benchmark_zobrist_vs_bit_packing.py
"""

import sys
import argparse
from pathlib import Path

from backend.solver.benchmark import BenchmarkSuite
from backend.solver.heuristics import combined_heuristic


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Zobrist hashing vs. bit-packing for A* FreeCell solver"
    )
    parser.add_argument(
        "--deals",
        type=int,
        nargs="+",
        default=list(range(1, 51)),  # Microsoft deals 1-50
        help="Deal numbers to benchmark (default: 1-50)",
    )
    parser.add_argument(
        "--weight",
        type=float,
        default=5.0,
        help="A* weight factor (default: 5.0)",
    )
    parser.add_argument(
        "--max-nodes",
        type=int,
        default=1000000,
        help="Maximum nodes to expand per deal (default: 1,000,000)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="experiment_logs/zobrist_benchmark.json",
        help="Output file for results",
    )

    args = parser.parse_args()

    # Create benchmark suite
    suite = BenchmarkSuite(
        deals=args.deals,
        weight=args.weight,
        heuristic_func=combined_heuristic,
    )

    # Run experiments
    results = suite.run(max_nodes_per_deal=args.max_nodes)

    # Print summary
    suite.print_summary()

    # Save results
    suite.save_results(output_file=args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
