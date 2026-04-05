# Testing Safeguard Frontend Display

## Quick Test Guide

### How to Test Safeguard Messages Display

#### Test 1: BFS Safeguard Trigger

```python
# In control_panel.py or board widget command handler:
from backend.model.state import GameState
from backend.solver.bfs import BFSAlgorithm

state = GameState()

# Create BFS with very small frontier limit to trigger safeguard
bfs = BFSAlgorithm(state, max_frontier_size=50)  # Very low limit

# Run search
path = bfs.search()

# Check feedback
feedback = bfs.get_user_feedback()
print(feedback)
# Output: "BFS terminated early: frontier size exceeded limit (50).
#          This typically happens due to exponential branching..."
```

#### Test 2: Through Frontend Thread

```python
# Start a game in the UI
# Click on a solver button (BFS/DFS)
# The status bar should show:

# Case 1 - Normal success:
# "Found a solution in 15 moves (342.51ms). Use List of move / Continue to review."

# Case 2 - Safeguard triggers (if limit is small):
# "BFS: BFS terminated early: frontier size exceeded limit (100000).
#  This typically happens due to exponential branching..."
```

### Manual Integration Test

1. **Add BFS with frontier limit to control panel:**
   ```python
   # In frontend/control_panel.py
   algos = {
       "BFS": lambda s: BFSAlgorithm(s, max_frontier_size=100_000),
       "DFS": lambda s: DFSAlgorithm(s, max_frontier_size=100_000),
       "UCS": lambda s: UCSAlgorithm(s),
       "A*": lambda s: AStarAlgorithm(s, weight=5.0),
   }
   ```

2. **Run the application:**
   ```bash
   python -m main
   ```

3. **Start a game and use a solver:**
   - The safeguard message should display in the status bar
   - Message clearly indicates why search stopped
   - Provides actionable recommendations

### Expected Messages

#### ✅ BFS Safeguard Message:
```
BFS: BFS terminated early: frontier size exceeded limit (100,000).
This typically happens due to exponential branching.
Consider using a more informed search algorithm (UCS, A*) or 
increasing the frontier limit.
```

#### ✅ DFS Safeguard Message:
```
DFS: DFS terminated early: frontier size exceeded limit (100,000).
This typically happens due to deep recursion or infinite paths.
Consider reducing the frontier limit or using a different search algorithm.
```

#### ✅ Generic Failure (no solution, no safeguard):
```
BFS failed to find a solution after 5234.23ms.
```

#### ✅ Success:
```
Found a solution in 15 moves (342.51ms). Use List of move / Continue to review.
```

---

## Flow Verification Checklist

- [ ] BFS/DFS have `get_user_feedback()` method ✓
- [ ] SearchAlgorithm stores algorithm instances ✓
- [ ] SearchAlgorithm has `get_algorithm_instance()` method ✓
- [ ] SolverThread extracts feedback ✓
- [ ] SolverThread emits tuple `(path, feedback)` ✓
- [ ] BoardSolverMixin unpacks tuple ✓
- [ ] BoardSolverMixin displays feedback message ✓
- [ ] Status bar shows message to user ✓

---

## Code Snippets to Verify

### 1. Check BFS has feedback method:
```python
from backend.solver.bfs import BFSAlgorithm
bfs = BFSAlgorithm(state)
assert hasattr(bfs, 'get_user_feedback'), "BFS missing get_user_feedback()"
```

### 2. Check SearchAlgorithm exposes instances:
```python
from backend.solver.algorithms import SearchAlgorithm
solver = SearchAlgorithm(state)
bfs_algo = solver.get_algorithm_instance("BFS")
assert bfs_algo is not None, "SearchAlgorithm can't get BFS instance"
```

### 3. Check SolverThread emits tuple:
```python
from frontend.board.solver_thread import SolverThread
thread = SolverThread(state, "BFS")
# After thread.run(), check result in result_ready signal
# Should be tuple: (path, feedback)
```

---

## Integration Status

| Component | Status |
|-----------|--------|
| BFS Safeguard | ✅ Implemented |
| DFS Safeguard | ✅ Implemented |
| get_user_feedback() | ✅ Implemented |
| SearchAlgorithm instance accessor | ✅ Implemented |
| SolverThread feedback extraction | ✅ Implemented |
| Frontend display integration | ✅ Implemented |

---

## Known Limitations

- Only `BFSAlgorithm` and `DFSAlgorithm` currently have `get_user_feedback()`
- Max frontier size must be set explicitly (not auto-detected)
- Feedback only shown when search returns `None` (no solution)

---

## Future Enhancements

1. Add `max_frontier_size` parameter to UI controls
2. Add `get_user_feedback()` to UCS/A* for consistency
3. Real-time progress updates during search
4. Detailed statistics popup dialog
5. Persistent logging of solver runs
