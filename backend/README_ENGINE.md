# FreeCell Game Engine - Documentation

## Overview

The `engine.py` module implements the core game logic for FreeCell, providing:
- **Move validation** - Check if moves follow FreeCell rules
- **State transitions** - Apply moves to game states
- **Goal checking** - Determine if the game is won
- **Search support** - Generate valid moves for AI search algorithms

---

## Design Philosophy

### Why Immutable State (`frozen=True` in models.py)?

```python
State(tableau, freecells, foundations)  # immutable tuple structure
```

**Problem**: Search algorithms (BFS, A*, DFS) need to explore thousands of states. If we modify states in place, the algorithm gets confused.

**Solution**: Make `State` immutable (frozen) so:
1. ✅ Old states remain unchanged during exploration
2. ✅ States can be stored in Python `set()` (visited nodes)
3. ✅ Algorithm can safely backtrack to previous states
4. ✅ Each move creates a NEW state, preserving history

**Implementation**:
- `State.__init__()` uses `object.__setattr__()` to convert lists to tuples (read-only)
- `State.__hash__()` enables storing in sets for fast lookup
- `State.__eq__()` compares states for visited set management

---

## Core Algorithm: get_valid_moves()

### Workflow (3 Steps)

```
INPUT: Current game state
  ↓
STEP 1: Scan Sources
  └─→ Extract movable sequences from tableau columns
  └─→ Extract single cards from freecells
  └─→ Result: List of things that can be moved
  ↓
STEP 2: Scan Destinations
  └─→ For each movable sequence, try all possible destinations:
      • 8 tableau columns
      • 4 foundation piles
      • 4 freecells
  └─→ Check validity with can_move_to_*() functions
  └─→ Result: All valid Move objects
  ↓
STEP 3: Apply Supermove Rule
  └─→ Filter sequences exceeding max length K = (F + 1) × 2^E
  └─→ Result: Legal moves respecting FreeCell physics
  ↓
OUTPUT: List of valid Move objects for search algorithm
```

### Why Return ALL Moves?

Search algorithms need complete options to make intelligent decisions:

```
State A (current position)
  ├─ Move 1 → State B (15 cards home) [evaluate with heuristic]
  ├─ Move 2 → State C (10 cards home) [evaluate with heuristic]
  ├─ Move 3 → State D (20 cards home) [evaluate with heuristic] ← BEST
  └─ ...more moves...

Algorithm picks Move 3 (highest heuristic) and repeats from State D
Without all moves, algorithm would be "blind"
```

---

## Function Breakdown

### 1. `can_move_to_foundation(card, foundation)`
**Purpose**: Check if a card can move to a foundation pile

**Rules**:
- Foundation empty → Only Ace (A) allowed
- Foundation has cards → Card must:
  - Match suit with pile (e.g., 5♥ on 4♥)
  - Rank exactly +1 (e.g., 5 on top of 4)

**Example**:
```python
foundation = (A♥, 2♥, 3♥)
card = 4♥  →  True (next in sequence)
card = 5♥  →  False (rank gap too large)
card = 4♠  →  False (wrong suit)
```

---

### 2. `can_move_to_tableau(card, tableau_col)`
**Purpose**: Check if a card can move to a tableau column

**Rules**:
- Column empty → Any card allowed
- Column has cards → Card must:
  - Rank exactly -1 (e.g., 5 on top of 6)
  - Color opposite (red ♥♦ on black ♣♠)

**Example**:
```python
column = [..., 6♥] (red)
card = 5♠  →  True  (rank 5, black)
card = 5♥  →  False (same color)
card = 4♠  →  False (rank gap)
```

---

### 3. `get_movable_sequences(column)`
**Purpose**: Extract all valid movable sequences from a column's top

**Why sequences?**  
In FreeCell, we can move multiple cards as a block if they form a valid sequence. This lets the AI explore more move options.

**Algorithm**:
1. Start at top card: `[K]`
2. Check card below: Q → Different color? ✓ Rank -1? ✓ → Add it: `[K, Q]`
3. Check next: J → Rules OK? → Add it: `[K, Q, J]`
4. Check next: 10 → Rules broken? → Stop

**Returns list of ALL valid sequences**: `[[K], [K, Q], [K, Q, J]]`

**Example**:
```
Column: [A♠, 8♥, 7♠, 6♥, 5♠, 4♦, 3♣]
                           ↑ top

Returns:
- [3♣]
- [4♦, 3♣]
- [5♠, 4♦, 3♣]
(Stops: 6♥ is red, 5♠ is black → same color, violates rule)
```

---

### 4. `_is_valid_sequence_pair(card1, card2)`
**Purpose**: Check if two adjacent cards form a valid sequence pair (internal helper)

**Conditions**:
- `card1.rank` must be exactly 1 higher than `card2.rank`
- `card1.color` must differ from `card2.color`

```python
# Valid pairs
(6♥, 5♠)  ✓  rank: 6 > 5 by 1, color: red ≠ black
(K♣, Q♦)  ✓  rank: K > Q by 1, color: black ≠ red

# Invalid pairs
(6♥, 5♥)  ✗  same color
(6♥, 4♠)  ✗  rank gap
```

---

### 5. `find_valid_destinations(state, sequence, from_pos)`
**Purpose**: Find all legal destinations for a movable sequence

**Scans 3 destination types**:

| Destination | Single Card | Sequence | Rule |
|---|---|---|---|
| **Foundation** | ✅ | ❌ | Same suit, rank+1 |
| **Tableau** | ✅ | ✅ | Rank-1, opposite color |
| **Freecell** | ✅ | ❌ | Empty cell only |

**Example**:
```python
sequence = [6♥, 5♠]
from_pos = ('tableau', 2)

Destinations checked:
- 4 Foundations (only if single card)
- 8 Tableau columns (any sequence)
- 4 Freecells (only if single card + empty)

Result: List of valid Move objects
```

---

### 6. `get_max_sequence_length(state)`
**Purpose**: Calculate maximum sequence length using supermove rule

**Supermove Rule** (Constraint Physics):
$$K = (F + 1) \times 2^E$$

Where:
- $F$ = number of empty freecells
- $E$ = number of empty tableau columns
- $K$ = max cards that can move as one sequence

**Why?**  
Each empty freecell and empty column effectively doubles your moving capacity. This models real FreeCell physics.

**Example**:
```python
state: 2 empty freecells, 1 empty column
K = (2 + 1) × 2^1 = 3 × 2 = 6

→ Can move sequences up to 6 cards
→ Sequences with 7+ cards are filtered out
```

---

### 7. `get_valid_moves(state)`
**Purpose**: Generate all legal moves from current state

**Workflow**:
```python
1. max_seq_len = get_max_sequence_length(state)
2. for each tableau column:
   - sequences = get_movable_sequences(column)
   - for each sequence:
     - if len(sequence) <= max_seq_len:  # Supermove rule
       - destinations = find_valid_destinations(state, sequence, pos)
       - add all destinations to moves list
3. for each freecell with a card:
   - destinations = find_valid_destinations(state, [card], pos)
   - add all destinations to moves list
4. return moves
```

**Complexity**:
- Time: O(columns × sequences × destinations) ≈ O(n) where n = movable cards
- Space: O(m) where m = valid moves (typically 20-50 per state)

---

### 8. `apply_move(state, move)`
**Purpose**: Execute a move and return new state

**Implementation** (Immutability Pattern):

```python
# Step 1: Deep copy all structures
new_tableau = [list(col) for col in state.tableau]
new_freecells = list(state.freecells)
new_foundations = [list(f) for f in state.foundations]

# Step 2: Modify copies
if from_type == 'tableau':
    new_tableau[from_idx].pop()
elif from_type == 'freecell':
    new_freecells[from_idx] = None

if to_type == 'tableau':
    new_tableau[to_idx].append(move.card)
elif to_type == 'freecell':
    new_freecells[to_idx] = move.card
elif to_type == 'foundation':
    new_foundations[to_idx].append(move.card)

# Step 3: Create new state (old state unchanged)
return State(new_tableau, new_freecells, new_foundations)
```

**Why this pattern?**
- Old `state` remains untouched → Safe for search backtracking
- New `state` is immutable → Can be stored in visited set
- Deterministic transitions → Search algorithm stability

---

### 9. `is_goal(state)`
**Purpose**: Check if game is won

**Win Condition**:
- All 4 foundations have exactly 13 cards each
- (Tableau and freecells become empty automatically)

```python
# All foundations complete
foundation_hearts = [A, 2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K]  ✓ 13 cards
foundation_diamonds = [A, 2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K]  ✓ 13 cards
foundation_clubs = [A, 2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K]  ✓ 13 cards
foundation_spades = [A, 2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K]  ✓ 13 cards

→ is_goal() returns True ✓
```

---

## Data Flow Example

### Scenario: One Move

```
Initial State:
  Tableau: [[A♠, 6♥, 5♠], [K♦], [], ...]
  Freecells: [None, None, None, None]
  Foundations: [[], [], [], []]

Call: moves = get_valid_moves(state)
  1. scan_movable_sequences():
     - Column 0: [[5♠], [6♥, 5♠]]
     - Column 1: [[K♦]]
  2. find_valid_destinations():
     - [5♠] from tableau[0] → Can go to freecell[0] or foundation (no)
     - [6♥, 5♠] from tableau[0] → Can go to tableau[1] (no, K♦ is king)
     - [K♦] from tableau[1] → Can go to freecell, tableau (empty columns ok)
  3. apply_supermove_rule:
     - F = 4 empty freecells, E = 6 empty columns
     - K = (4+1) × 2^6 = 320 (generous limit)
     - All sequences pass

Result: moves = [Move(5♠, from tableau[0], to freecell[0]), ...]

Select: moves[0] (AI heuristic picks best)

Call: new_state = apply_move(state, moves[0])
  - Removes 5♠ from tableau[0]
  - Adds 5♠ to freecell[0]
  - Returns new State object

new_state:
  Tableau: [[A♠, 6♥], [K♦], [], ...]
  Freecells: [5♠, None, None, None]
  Foundations: [[], [], [], []]

Call: is_goal(new_state) → False (foundations empty)

Continue with next move from new_state...
```

---

## Key Design Decisions & Rationale

| Decision | Reason |
|----------|--------|
| **Immutable State** | Search algo needs stable state history for backtracking |
| **Return ALL moves** | AI needs complete options to evaluate heuristic |
| **Sequence extraction** | Reduces search branching, mimics how humans play |
| **Supermove rule** | Enforces real FreeCell physics constraints |
| **Tuple storage** | Immutability + hashability for visited set |
| **Deep copy in apply_move** | Preserves old state for search tree exploration |
| **Separate validation functions** | Reusable, testable, clear responsibility |

---

## Testing Ideas

```python
# Test valid foundation move
state = create_test_state()
assert can_move_to_foundation(Card('hearts', 'A'), tuple()) == True
assert can_move_to_foundation(Card('hearts', '2'), 
                               tuple([Card('hearts', 'A')])) == True

# Test sequence extraction
column = (A♠, 8♥, 7♠, 6♥, 5♠)
sequences = get_movable_sequences(column)
assert len(sequences) == 3
assert sequences[0] == [5♠]
assert sequences[2] == [8♥, 7♠, 6♥, 5♠]

# Test state immutability
state1 = create_test_state()
state2 = apply_move(state1, move)
assert state1.tableau == original_state.tableau  # unchanged

# Test supermove rule
state = create_state(empty_freecells=2, empty_columns=1)
K = get_max_sequence_length(state)
assert K == (2+1) * (2**1) == 6
```

---

## References

- **Models**: `models.py` - State, Move, Card definitions
- **FreeCell Rules**: https://en.wikipedia.org/wiki/FreeCell
- **Search Integration**: Used by BFS/A* in `algorithms.py`
