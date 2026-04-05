# Frontend Integration: Safeguard Feedback Display

## Problem Identified

The safeguard mechanism was **not displaying messages on the frontend** because:

1. **SolverThread** only emitted the `path` result (None on safeguard trigger)
2. **BoardSolverMixin** showed generic message: "failed to find a solution"
3. Detailed safeguard feedback from BFS/DFS was **never extracted or displayed**

---

## Solution Implemented

### 1. **SearchAlgorithm Enhancement** (`backend/solver/algorithms.py`)

**Before:**
```python
self._handlers = {
    "BFS": BFSAlgorithm(...).search,
    "DFS": DFSAlgorithm(...).search,
    ...
}
```

**After:**
```python
# Store algorithm instances for method access
self.bfs_instance = BFSAlgorithm(...)
self.dfs_instance = DFSAlgorithm(...)
...

# Map algorithm names to instances
self._instances = {
    "BFS": self.bfs_instance,
    "DFS": self.dfs_instance,
    ...
}

# Added method to retrieve algorithm instances
def get_algorithm_instance(self, algorithm: str):
    return self._instances.get(algorithm)
```

---

### 2. **SolverThread Enhancement** (`frontend/board/solver_thread.py`)

**Changes:**
- Added `self.solver` attribute to keep algorithm instance
- Added `_extract_feedback()` method to get user feedback from algorithm
- Modified `run()` to emit tuple: `(path, feedback_message)` instead of just `path`

**New Signal Emission:**
```python
# Before
self.result_ready.emit(path)

# After
feedback = self._extract_feedback(path)
self.result_ready.emit((path, feedback))
```

**Feedback Extraction:**
```python
def _extract_feedback(self, path):
    if not self.solver:
        return None
    
    algo_instance = self.solver.get_algorithm_instance(self.algo)
    if algo_instance is None:
        return None
    
    if hasattr(algo_instance, "get_user_feedback"):
        try:
            feedback = algo_instance.get_user_feedback()
            return feedback if feedback else None
        except Exception:
            return None
    
    return None
```

---

### 3. **BoardSolverMixin Enhancement** (`frontend/board/solver_mixin.py`)

**Before:**
```python
def _on_solver_finished(self, algo, path, run_id):
    if path is None:
        self._emit_status(f"{algo} failed to find a solution...")
```

**After:**
```python
def _on_solver_finished(self, algo, result, run_id):
    # Handle both tuple (path, feedback) and legacy path-only format
    if isinstance(result, tuple) and len(result) == 2:
        path, feedback = result
    else:
        path = result
        feedback = None
    
    if path is None:
        # Use safeguard feedback if available
        if feedback:
            self._emit_status(f"{algo}: {feedback}")
        else:
            self._emit_status(f"{algo} failed to find a solution...")
```

---

## Data Flow Diagram

```
┌─────────────────┐
│ BoardWidget     │
│ solve_with_algo │
└────────┬────────┘
         │
         ↓
┌─────────────────────────────────┐
│ SolverThread.run()              │
│ - Create SearchAlgorithm        │
│ - Call search(algo)             │
│ - Extract feedback (NEW!)       │
│ - Emit (path, feedback) (NEW!)  │
└────────┬────────────────────────┘
         │
         ↓
┌──────────────────────────────────────┐
│ SearchAlgorithm                      │
│ - Has get_algorithm_instance() (NEW!)│
│ - Returns BFSAlgorithm instance      │
└──────────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────┐
│ BFSAlgorithm                         │
│ - get_user_feedback() (EXISTS!)      │
│ - Checks termination_reason          │
│ - Returns safeguard message          │
└──────────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────┐
│ result_ready signal emitted          │
│ (path, "BFS terminated early...")    │
└────────┬─────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────┐
│ BoardSolverMixin._on_solver_finished │
│ - Unpack (path, feedback)            │
│ - Display feedback to user (NEW!)    │
└──────────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────┐
│ _emit_status()                       │
│ Updates UI with message              │
└──────────────────────────────────────┘
```

---

## Messages Displayed on Frontend

### BFS Frontier Limit Exceeded
```
BFS: BFS terminated early: frontier size exceeded limit (100,000).
This typically happens due to exponential branching.
Consider using a more informed search algorithm (UCS, A*) or 
increasing the frontier limit.
```

### DFS Frontier Limit Exceeded
```
DFS: DFS terminated early: frontier size exceeded limit (100,000).
This typically happens due to deep recursion or infinite paths.
Consider reducing the frontier limit or using a different search algorithm.
```

### No Solution Found (Generic)
```
BFS failed to find a solution after 5234.23ms.
```

### Already Solved
```
BFS reports already solved after 12.34ms.
```

### Success
```
Found a solution in 15 moves (342.51ms). Use List of move / Continue to review.
```

---

## Testing the Integration

### Test Scenario: BFS with Small Frontier Limit

```python
# In control_panel.py or board widget
bfs = BFSAlgorithm(state, max_frontier_size=100)

# When safeguard triggers:
# 1. search() returns None
# 2. get_user_feedback() returns safeguard message
# 3. SolverThread emits (None, "BFS terminated early...")
# 4. BoardSolverMixin displays it to user
```

**Expected UI Output:**
```
Status Bar: "BFS: BFS terminated early: frontier size exceeded limit (100).
This typically happens due to exponential branching.
Consider using a more informed search algorithm (UCS, A*) or 
increasing the frontier limit."
```

---

## Backward Compatibility

✅ **Fully backward compatible**:
- Old code emitting just `path` still works
- New code emits `(path, feedback)` tuple
- `_on_solver_finished` handles both formats gracefully

```python
if isinstance(result, tuple) and len(result) == 2:
    path, feedback = result
else:
    path = result  # Legacy format
    feedback = None
```

---

## Files Modified

| File | Changes |
|------|---------|
| `backend/solver/algorithms.py` | Store algorithm instances, add getter method |
| `frontend/board/solver_thread.py` | Extract feedback, emit tuple |
| `frontend/board/solver_mixin.py` | Handle feedback in solver finish callback |

---

## Summary

✅ **Safeguard messages NOW display on frontend**
- User-friendly feedback from BFS/DFS safeguards
- Clear explanation of why search stopped
- Practical recommendations for next steps
- Full backward compatibility maintained

The data flows seamlessly from algorithm → thread → UI widget → status bar/dialog!
