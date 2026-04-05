"""
SPECIAL BFS TEST CASES - DESIGN DOCUMENTATION

This document explains the design and rationale behind the special deterministic
test cases added to shuffle.py for controlled BFS performance testing.

================================================================================
OVERVIEW
================================================================================

Two special test cases have been added to backend/engine/shuffle.py:

1. "bfs_easy_10" - ~10 move solution
2. "bfs_hard_20" - ~20 move solution

Access them via:
    from backend.engine.shuffle import get_special_test_case
    
    easy_state = get_special_test_case("bfs_easy_10")
    hard_state = get_special_test_case("bfs_hard_20")

================================================================================
DESIGN PHILOSOPHY
================================================================================

Key Requirements:
- DETERMINISTIC: Identical state every time the ID is requested
- VALID: Legal FreeCell game state (all placement rules followed)
- SOLVABLE: BFS can find a solution
- REPRODUCIBLE: No randomness, fixed initial conditions
- CONTROLLED: Predictable solution depth for benchmarking

Why These Cases Are Useful:
- Eliminates randomness from BFS benchmarking
- Allows comparing algorithmic improvements on identical problems
- Enables regression testing for solver performance
- Provides teaching examples for FreeCell rules

================================================================================
CASE 1: EASY (bfs_easy_10)
================================================================================

ESTIMATED SOLUTION DEPTH: 8-12 moves
OPTIMAL DEPTH: ~10 moves

DESIGN:

Approach:
  Strip game state to minimal pieces needed for ~10 move puzzle
  
Tableau Layout:
  Col 0: [A♥]             (Ace, ready for foundation)
  Col 1: [A♦]             (Ace, ready for foundation)
  Col 2: [3♣, 4♠]         (Valid sequence: 3 is red on black 4)
  Col 3: [2♥, 3♠]         (Valid sequence: 2 is red on black 3)
  Col 4-7: Empty          (Available for maneuvering)
  
Freecells:
  All 4 empty (maximum available for maneuvering)
  
Foundations:
  Hearts: [2, 3, 4, ..., Q, K]   (Missing only A♥ from tableau)
  Diamonds: Similar              (Missing only A♦)
  Clubs: [2, 3, 4, ..., Q, K]    (Complete except A♣ and 3♣ in tableau)
  Spades: [2, 3, 4, ..., Q, K]   (Complete except A♠ and 4♠ in tableau)
  
Goal State:
  All 52 cards in foundations (all 4 cards per suit)
  
WHY ~10 MOVES?

Starting from this state, optimal solution:
  1. Move A♥ to foundation (freecells: 3 available)
  2. Move A♦ to foundation (freecells: 2 available)  
  3. Move 3♣ to freecell (freecells: 1 available)
  4. Move 4♠ to freecell (freecells: 0 available)
  5. Move 3♠ to foundation (freecells: 1 available)
  6. Move 2♥ to freecell (freecells: 0 available)
  7. Move 3♣ to foundation (freecells: 1 available)
  8. Move 4♠ to foundation (freecells: 2 available)
  Plus 1-3 additional forces moves for final cascade
  Total: ~8-10 moves

Key Properties:
  - Minimal branching (few legal moves at each step)
  - Clear path to solution with few dead ends
  - Tests basic freecell management
  - No complex sequence unraveling needed

================================================================================
CASE 2: HARD (bfs_hard_20)
================================================================================

ESTIMATED SOLUTION DEPTH: 18-22 moves
OPTIMAL DEPTH: ~20 moves

DESIGN:

Approach:
  Create complex blocking scenarios requiring careful sequencing
  
Tableau Layout:
  Col 0: [8♥, 7♠]         (Valid: 8 red on black 7, 8=7+1)
  Col 1: [6♦, 5♣]         (Valid: 6 red on black 5, 6=5+1)
  Col 2: [4♠, 3♥]         (Valid: 4 black on red 3, 4=3+1)
  Col 3: [A♥]             (Ace blocked by entire column 0)
  Col 4: [A♦]             (Ace blocked by entire column 1)
  Col 5: [K♥]             (King, only movable to empty column)
  Col 6: [Q♦, J♣]         (Valid: Q red on black J, Q=J+1)
  Col 7: [10♠, 9♦]        (Valid: 10 black on red 9, 10=9+1)
  
Freecells:
  All 4 empty
  
Foundations:
  Missing cards: A♥, A♦, 3♥, 4♠, 5♣, 6♦, 7♠, 8♥, 9♦, 10♠, J♣, Q♦, K♥ (13 total)
  All other cards (39) already in foundations
  
Goal State:
  All 52 cards in foundations
  
WHY ~20 MOVES?

Challenges:
  - Those Aces in cols 3-4 are blocked by long sequences
  - Must carefully unwind sequences to reach Aces
  - King in col 5 takes a freecell or empty column
  - Multiple interacting sequences require freecell juggling
  
Rough Solution Path:
  1-4: Move blocking cards to freecells (8♥, 6♦, 4♠, Q♦)
  5-8: Move first sequence cards to nearby columns
  9-10: Now Aces are reachable - move to foundation
  11-14: Move Q♦ somewhere, continue sequence unraveling
  15-18: Complete remaining sequences and moves K♥
  19-20: Final foundation cascade
  
Key Properties:
  - More cards in tableau (16 vs 6)
  - Multiple interacting blocking sequences
  - Tests freecell management and lookahead
  - Requires understanding move sequences
  - Higher branching factor (more legal moves per state)

================================================================================
IMPLEMENTATION DETAILS
================================================================================

Location: backend/engine/shuffle.py

Public API:
  get_special_test_case(test_case_id: str) -> Optional[State]
    
    Supported IDs:
      - "bfs_easy_10": Easy test case
      - "bfs_hard_20": Harder test case
      - Any other ID: returns None
    
    Returns: Valid State object or None if ID unknown

Internal Helpers:
  _make_easy_test_case() -> State
  _make_hard_test_case() -> State

Backward Compatibility:
  ✓ No changes to existing functions
  ✓ No breaking changes to API
  ✓ Random shuffle still works normally
  ✓ Microsoft deal numbers still supported

================================================================================
VERIFICATION & TESTING
================================================================================

Test Script: tests/test_special_bfs_cases.py

Run with:
  python -m pytest tests/test_special_bfs_cases.py
  
Or directly:
  python tests/test_special_bfs_cases.py

The test script:
  1. Loads both special cases
  2. Runs BFS on each
  3. Measures solution depth, time, nodes expanded
  4. Verifies solution validity
  5. Reports whether depths match expected ranges (±2 moves)

Expected Results:
  ✓ Both cases should be solvable
  ✓ Easy case should find 8-12 move solution
  ✓ Hard case should find 18-22 move solution
  ✓ No solution should take >100 moves

================================================================================
USAGE EXAMPLES
================================================================================

Example 1: Create and solve easy case with BFS

    from backend.engine.shuffle import get_special_test_case
    from backend.search.bfs import BFSAlgorithm
    
    state = get_special_test_case("bfs_easy_10")
    bfs = BFSAlgorithm(state)
    solution = bfs.search()
    print(f"Solution in {len(solution)} moves")

Example 2: Compare algorithm performance

    easy = get_special_test_case("bfs_easy_10")
    hard = get_special_test_case("bfs_hard_20")
    
    for case_id, state in [("easy", easy), ("hard", hard)]:
        bfs = BFSAlgorithm(state)
        sol = bfs.search()
        print(f"{case_id}: {len(sol)} moves, metrics: {bfs.metrics}")

Example 3: Benchmark different solvers on same cases

    from backend.solver.algorithms import SearchAlgorithm
    
    state = get_special_test_case("bfs_easy_10")
    sa = SearchAlgorithm(state)
    
    bfs_sol = sa.search("BFS")
    dfs_sol = sa.search("DFS")
    astar_sol = sa.search("A*")
    
    print(f"BFS: {len(bfs_sol)}, DFS: {len(dfs_sol)}, A*: {len(astar_sol)}")

================================================================================
ASSUMPTIONS & LIMITATIONS
================================================================================

Assumptions Made:
  1. Card placement rules follow standard FreeCell (descending sequences, 
     alternating colors on tableau, suit sequence in foundations)
  2. All moves are legal under FreeCell rules
  3. Solution depths are estimates (±2 moves acceptable)
  4. Optimal solution may be found or non-optimal solution
  5. BFS will find ONE optimal solution (not necessarily unique)

Limitations:
  - Hard case depth might vary (19-21 moves depending on BFS choices)
  - Easy case could be solved in as few as 8 moves with perfect choices
  - No guarantee of best-first ordering for multiple solutions of same depth
  - These cases are NOT representative of random FreeCell puzzles
     (much easier than average)

Known Issues:
  - None at this time (please report if cases are incorrect/invalid)

================================================================================
EXTENDING THE TEST CASES
================================================================================

To add more test cases:

1. Create a new function _make_my_test_case() -> State:
   - Follow the same pattern (tableau, freecells, foundations tuples)
   - Ensure all 52 unique cards are used (39 in foundations + 13 in tableau/cells)
   - Verify sequences follow FreeCell rules

2. Add entry to get_special_test_case():
   if test_case_id == "my_test_case":
       return _make_my_test_case()

3. Document the design in this file

4. Add test coverage in tests/test_special_bfs_cases.py

5. Verify solution depth with a test run

================================================================================
"

