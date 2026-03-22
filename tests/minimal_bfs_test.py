"""Minimal BFS test."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.engine.shuffle import deal_by_game_number
from backend.model.state import State
from backend.solver.algorithms import SearchAlgorithm
import time

deal_num = 1
tableau = deal_by_game_number(deal_num)
state = State.from_lists(
    tableau=tableau,
    freecells=[None] * 4,
    foundations=[[] for _ in range(4)]
)

print(f"Deal #{deal_num}")
print(f"Initial state is_goal: {state.is_goal}")

searcher = SearchAlgorithm(state)

print("Running BFS (with 2-second timeout by stopping)...")
start = time.perf_counter()
try:
    path = searcher.search("BFS")
    elapsed = time.perf_counter() - start
    print(f"BFS completed in {elapsed:.2f}s")
    print(f"Path: {path}")
    print(f"Path length: {len(path) if path else 0}")
except Exception as e:
    elapsed = time.perf_counter() - start
    print(f"BFS error after {elapsed:.2f}s: {e}")
    import traceback
    traceback.print_exc()
