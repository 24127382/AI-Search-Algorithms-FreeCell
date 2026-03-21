"""Minimal DFS test."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.engine.shuffle import deal_by_game_number
from backend.model.state import State
from backend.solver.dfs import DFSAlgorithm
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

solver = DFSAlgorithm(state)

print("Running DFS (with 5-second timeout concept)...")
start = time.perf_counter()
try:
    path = solver.search()
    elapsed = time.perf_counter() - start
    if path is not None:
        print(f"DFS completed in {elapsed:.2f}s, path length: {len(path)}")
    else:
        print(f"DFS failed to find solution in {elapsed:.2f}s")
except KeyboardInterrupt:
    print("DFS interrupted")
except Exception as e:
    print(f"DFS error: {e}")
