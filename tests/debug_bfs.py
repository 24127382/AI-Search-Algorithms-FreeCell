"""Debug BFS behavior."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.engine.shuffle import deal_by_game_number
from backend.model.state import State
from backend.engine.engine import get_valid_moves
from backend.solver.bfs import BFSAlgorithm

def build_initial_state(deal_number: int) -> State:
    """Create initial game state from deal number."""
    tableau = deal_by_game_number(deal_number)
    return State.from_lists(
        tableau=tableau,
        freecells=[None] * 4,
        foundations=[[] for _ in range(4)]
    )

# Test Deal #1
deal_num = 1
state = build_initial_state(deal_num)

print(f"Initial state is_goal: {state.is_goal}")
print(f"Initial state hashable: {hash(state)}")

valid_moves = get_valid_moves(state)
print(f"Valid moves count: {len(valid_moves)}")
print(f"First 5 valid moves: {valid_moves[:5]}")

# Test BFS
print("\nRunning BFS...")
bfs = BFSAlgorithm(state)
path = bfs.search()
print(f"BFS result: {path}")
print(f"Path type: {type(path)}")
