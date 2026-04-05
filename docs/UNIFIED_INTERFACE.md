# Using the Unified `generate_game()` Interface

The `generate_game()` function provides a unified entry point for generating FreeCell game states from both Microsoft deal numbers and special deterministic test cases.

## Quick Start

```python
from backend.engine.shuffle import generate_game

# Load a Microsoft deal (integer)
state1 = generate_game(42)

# Load a special test case (string)
state2 = generate_game("bfs_easy_10")
state3 = generate_game("bfs_hard_20")

# All return State objects
print(f"Deal 42 is goal: {state2.is_goal}")
print(f"Easy case has {sum(len(col) for col in state3.tableau)} cards in tableau")
```

## Supported Special Test Cases

### `"bfs_easy_10"`
- **Description**: Easy deterministic test case
- **Approximate solution depth**: ~10 moves
- **Tableau cards**: 6 cards  
- **Foundations**: 46 cards already placed
- **Purpose**: Quick testing and validation

### `"bfs_hard_20"`
- **Description**: Harder deterministic test case
- **Approximate solution depth**: ~20 moves
- **Tableau cards**: 16 cards
- **Foundations**: 36 cards already placed
- **Purpose**: Challenging scenarios for algorithm benchmarking

## Return Type

Both integer and string inputs return a complete `State` object:

```python
from backend.model.state import State

state: State = generate_game(42)  # Type is State

# Access game components
tableau = state.tableau        # tuple[tuple[Card, ...], ...] - 8 columns
freecells = state.freecells    # tuple[Optional[Card], ...] - 4 slots
foundations = state.foundations # tuple[tuple[Card, ...], ...] - 4 stacks
is_goal = state.is_goal        # bool - True if all foundations are complete

# Count cards
total_cards = sum(len(col) for col in state.tableau)
total_cards += sum(1 for fc in state.freecells if fc is not None)
total_cards += sum(len(col) for col in state.foundations)
assert total_cards == 52
```

## Error Handling

Invalid string IDs raise `ValueError` with a helpful message:

```python
try:
    state = generate_game("invalid_id")
except ValueError as e:
    print(e)  # Unknown special test case ID: 'invalid_id'. 
              # Supported IDs: 'bfs_easy_10', 'bfs_hard_20'
```

Integer inputs are always valid (they represent Microsoft deal numbers in the range 0 to 2^63-1).

## Backward Compatibility

The original functions are still available and unchanged:

```python
# Old API still works
from backend.engine.shuffle import deal_by_game_number
tableau = deal_by_game_number(42)  # Returns tuple[tuple[Card, ...], ...]

# Manual State construction
from backend.model.state import State
state = State.from_lists(
    tableau=tableau,
    freecells=[None] * 4,
    foundations=[[] for _ in range(4)]
)
```

However, using `generate_game()` is recommended as it's more convenient and always returns a complete `State` object.

## Integration Examples

### With BFS Solver

```python
from backend.engine.shuffle import generate_game
from backend.search.bfs import BFSAlgorithm

state = generate_game("bfs_easy_10")
solver = BFSAlgorithm(max_search_depth=20)
solution = solver.solve(state)
```

### With Custom Experiments

```python
from backend.engine.shuffle import generate_game

# Test multiple cases
test_cases = [42, 100, 1000, "bfs_easy_10", "bfs_hard_20"]

for case_id in test_cases:
    state = generate_game(case_id)
    # ... run your algorithm on state
```

### Iterating Through Specific Scenarios

```python
from backend.engine.shuffle import generate_game

# Microsoft deals
microsoft_deals = [1, 2, 3, 42, 100]
for deal_num in microsoft_deals:
    state = generate_game(deal_num)
    # Process state

# Special test cases
special_cases = ["bfs_easy_10", "bfs_hard_20"]
for case_id in special_cases:
    state = generate_game(case_id)
    # Process state
```

## Performance Notes

- **Microsoft deals**: Fast (~1ms) - uses precomputed PRNG shuffle
- **Special test cases**: Very fast (~0.1ms) - returns hardcoded states
- **Memory**: Each call creates a new State object (~1KB - state is immutable)

## Testing

Run the validation suite:

```bash
python tests/test_generate_game.py
```

This verifies:
- Integer inputs work with Microsoft algorithm
- String inputs load special test cases
- Invalid string IDs raise errors
- Backward compatibility maintained
- Different inputs produce different states
- All 52 cards accounted for in each case
