"""
Zobrist Incremental Update Integration Verification & Benchmark

Compares:
1. Full recomputation approach (old)
2. Incremental update approach (new)
3. State hash (baseline)
"""

import time
import json
from pathlib import Path
from collections import deque
from dataclasses import dataclass, asdict
import random
import sys

sys.path.insert(0, str(Path(__file__).parent))

from backend.model.card import Card, VALID_SUITS, VALID_RANK
from backend.model.state import State
from backend.engine.engine import apply_move, get_valid_moves
from backend.solver.utils import ZobristHash, get_zobrist_table


@dataclass
class BenchmarkResult:
    """Results from a single benchmark"""
    method: str
    algorithm: str
    runtime_ms: float
    nodes_expanded: int
    hash_computations: int
    solution_found: bool
    avg_hash_time_us: float


def create_test_state(seed: int) -> State:
    """Create a deterministic test state"""
    random.seed(seed)
    
    all_cards = [Card(suit, rank) for suit in VALID_SUITS for rank in VALID_RANK]
    random.shuffle(all_cards)
    
    tableau = []
    idx = 0
    for i in range(8):
        col_size = random.randint(1, 7)
        tableau.append([all_cards[idx + j] for j in range(col_size)])
        idx += col_size
    
    remaining_cards = all_cards[idx:]
    freecells = remaining_cards[:4] + [None] * (4 - min(4, len(remaining_cards)))
    foundations = [[] for _ in range(4)]
    
    return State.from_lists(tableau, freecells, foundations)


def extract_move_details(state, move, new_state):
    """Extract source and destination details from a move"""
    try:
        from_type, from_idx = move.from_pos
        to_type, to_idx = move.to_pos
        card = move.card
        
        from_params = {}
        to_params = {}
        
        if from_type == "tableau":
            from_params = {"from_column": from_idx, "from_depth": len(state.tableau[from_idx]) - 1}
        elif from_type == "freecell":
            from_params = {"from_freecell": from_idx}
        elif from_type == "foundation":
            from_params = {"from_foundation": move.card.suit}
        
        if to_type == "tableau":
            to_params = {"to_column": to_idx, "to_depth": len(new_state.tableau[to_idx]) - 1}
        elif to_type == "freecell":
            to_params = {"to_freecell": to_idx}
        elif to_type == "foundation":
            to_params = {"to_foundation": move.card.suit}
        
        return card, from_params, to_params
    except (IndexError, AttributeError):
        return None


# =============================================================================
# OLD APPROACH: Full Recomputation (Baseline)
# =============================================================================

def bfs_full_recompute(initial_state, max_nodes=5000):
    """BFS with full zobrist recomputation per state"""
    zobrist_table = get_zobrist_table()
    start_time = time.perf_counter()
    
    queue = deque([(initial_state, [])])
    visited = set()
    nodes_expanded = 0
    hash_computations = 0
    hash_time = 0
    
    while queue and nodes_expanded < max_nodes:
        state, path = queue.popleft()
        
        # Full recomputation (old approach)
        hash_start = time.perf_counter()
        hasher = ZobristHash(zobrist_table)
        state_hash = hasher.hash_state(state)
        hash_time += time.perf_counter() - hash_start
        hash_computations += 1
        
        if state_hash in visited:
            continue
        visited.add(state_hash)
        nodes_expanded += 1
        
        if state.is_goal:
            elapsed = (time.perf_counter() - start_time) * 1000
            return BenchmarkResult(
                method="Full Recompute (Old)",
                algorithm="BFS",
                runtime_ms=elapsed,
                nodes_expanded=nodes_expanded,
                hash_computations=hash_computations,
                solution_found=True,
                avg_hash_time_us=hash_time * 1e6 / max(hash_computations, 1)
            )
        
        valid_moves = get_valid_moves(state)
        for move in valid_moves:
            new_state = apply_move(state, move)
            
            # Recompute hash for new state
            hash_start = time.perf_counter()
            new_hasher = ZobristHash(zobrist_table)
            new_hash = new_hasher.hash_state(new_state)
            hash_time += time.perf_counter() - hash_start
            hash_computations += 1
            
            if new_hash not in visited:
                queue.append((new_state, path + [move]))
    
    elapsed = (time.perf_counter() - start_time) * 1000
    return BenchmarkResult(
        method="Full Recompute (Old)",
        algorithm="BFS",
        runtime_ms=elapsed,
        nodes_expanded=nodes_expanded,
        hash_computations=hash_computations,
        solution_found=False,
        avg_hash_time_us=hash_time * 1e6 / max(hash_computations, 1)
    )


# =============================================================================
# NEW APPROACH: Incremental Updates
# =============================================================================

def bfs_incremental_update(initial_state, max_nodes=5000):
    """BFS with incremental zobrist updates"""
    zobrist_table = get_zobrist_table()
    start_time = time.perf_counter()
    
    # Initialize with full hash once
    initial_hasher = ZobristHash(zobrist_table)
    initial_hash = initial_hasher.hash_state(initial_state)
    
    queue = deque([(initial_state, [], initial_hasher)])
    visited = set()
    nodes_expanded = 0
    hash_computations = 1  # Initial full hash
    hash_time = 0
    
    while queue and nodes_expanded < max_nodes:
        state, path, state_hasher = queue.popleft()
        state_hash = state_hasher.get_hash()
        
        if state_hash in visited:
            continue
        visited.add(state_hash)
        nodes_expanded += 1
        
        if state.is_goal:
            elapsed = (time.perf_counter() - start_time) * 1000
            return BenchmarkResult(
                method="Incremental Update (New)",
                algorithm="BFS",
                runtime_ms=elapsed,
                nodes_expanded=nodes_expanded,
                hash_computations=hash_computations,
                solution_found=True,
                avg_hash_time_us=hash_time * 1e6 / max(hash_computations, 1)
            )
        
        valid_moves = get_valid_moves(state)
        for move in valid_moves:
            new_state = apply_move(state, move)
            
            # Try incremental update
            new_hasher = ZobristHash(zobrist_table)
            new_hasher.hash_state(state)  # Copy current state hash
            
            move_details = extract_move_details(state, move, new_state)
            if move_details:
                card, from_params, to_params = move_details
                hash_start = time.perf_counter()
                new_hasher.update_move(card, **from_params, **to_params)
                hash_time += time.perf_counter() - hash_start
                hash_computations += 1  # Count as one operation
            else:
                # Fallback to full hash
                hash_start = time.perf_counter()
                new_hasher.hash_state(new_state)
                hash_time += time.perf_counter() - hash_start
                hash_computations += 1
            
            new_hash = new_hasher.get_hash()
            if new_hash not in visited:
                queue.append((new_state, path + [move], new_hasher))
    
    elapsed = (time.perf_counter() - start_time) * 1000
    return BenchmarkResult(
        method="Incremental Update (New)",
        algorithm="BFS",
        runtime_ms=elapsed,
        nodes_expanded=nodes_expanded,
        hash_computations=hash_computations,
        solution_found=False,
        avg_hash_time_us=hash_time * 1e6 / max(hash_computations, 1)
    )


def dfs_full_recompute(initial_state, max_nodes=5000):
    """DFS with full zobrist recomputation per state"""
    zobrist_table = get_zobrist_table()
    start_time = time.perf_counter()
    
    stack = [(initial_state, [])]
    visited = set()
    nodes_expanded = 0
    hash_computations = 0
    hash_time = 0
    
    while stack and nodes_expanded < max_nodes:
        state, path = stack.pop()
        
        hash_start = time.perf_counter()
        hasher = ZobristHash(zobrist_table)
        state_hash = hasher.hash_state(state)
        hash_time += time.perf_counter() - hash_start
        hash_computations += 1
        
        if state_hash in visited:
            continue
        visited.add(state_hash)
        nodes_expanded += 1
        
        if state.is_goal:
            elapsed = (time.perf_counter() - start_time) * 1000
            return BenchmarkResult(
                method="Full Recompute (Old)",
                algorithm="DFS",
                runtime_ms=elapsed,
                nodes_expanded=nodes_expanded,
                hash_computations=hash_computations,
                solution_found=True,
                avg_hash_time_us=hash_time * 1e6 / max(hash_computations, 1)
            )
        
        valid_moves = get_valid_moves(state)
        for move in valid_moves:
            new_state = apply_move(state, move)
            
            hash_start = time.perf_counter()
            new_hasher = ZobristHash(zobrist_table)
            new_hash = new_hasher.hash_state(new_state)
            hash_time += time.perf_counter() - hash_start
            hash_computations += 1
            
            if new_hash not in visited:
                stack.append((new_state, path + [move]))
    
    elapsed = (time.perf_counter() - start_time) * 1000
    return BenchmarkResult(
        method="Full Recompute (Old)",
        algorithm="DFS",
        runtime_ms=elapsed,
        nodes_expanded=nodes_expanded,
        hash_computations=hash_computations,
        solution_found=False,
        avg_hash_time_us=hash_time * 1e6 / max(hash_computations, 1)
    )


def dfs_incremental_update(initial_state, max_nodes=5000):
    """DFS with incremental zobrist updates"""
    zobrist_table = get_zobrist_table()
    start_time = time.perf_counter()
    
    initial_hasher = ZobristHash(zobrist_table)
    initial_hash = initial_hasher.hash_state(initial_state)
    
    stack = [(initial_state, [], initial_hasher)]
    visited = set()
    nodes_expanded = 0
    hash_computations = 1
    hash_time = 0
    
    while stack and nodes_expanded < max_nodes:
        state, path, state_hasher = stack.pop()
        state_hash = state_hasher.get_hash()
        
        if state_hash in visited:
            continue
        visited.add(state_hash)
        nodes_expanded += 1
        
        if state.is_goal:
            elapsed = (time.perf_counter() - start_time) * 1000
            return BenchmarkResult(
                method="Incremental Update (New)",
                algorithm="DFS",
                runtime_ms=elapsed,
                nodes_expanded=nodes_expanded,
                hash_computations=hash_computations,
                solution_found=True,
                avg_hash_time_us=hash_time * 1e6 / max(hash_computations, 1)
            )
        
        valid_moves = get_valid_moves(state)
        for move in valid_moves:
            new_state = apply_move(state, move)
            
            new_hasher = ZobristHash(zobrist_table)
            new_hasher.hash_state(state)
            
            move_details = extract_move_details(state, move, new_state)
            if move_details:
                card, from_params, to_params = move_details
                hash_start = time.perf_counter()
                new_hasher.update_move(card, **from_params, **to_params)
                hash_time += time.perf_counter() - hash_start
                hash_computations += 1
            else:
                hash_start = time.perf_counter()
                new_hasher.hash_state(new_state)
                hash_time += time.perf_counter() - hash_start
                hash_computations += 1
            
            new_hash = new_hasher.get_hash()
            if new_hash not in visited:
                stack.append((new_state, path + [move], new_hasher))
    
    elapsed = (time.perf_counter() - start_time) * 1000
    return BenchmarkResult(
        method="Incremental Update (New)",
        algorithm="DFS",
        runtime_ms=elapsed,
        nodes_expanded=nodes_expanded,
        hash_computations=hash_computations,
        solution_found=False,
        avg_hash_time_us=hash_time * 1e6 / max(hash_computations, 1)
    )


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*70)
    print("ZOBRIST INCREMENTAL UPDATE INTEGRATION VERIFICATION")
    print("="*70)
    print("\nComparing old (full recompute) vs new (incremental) approaches\n")
    
    results = []
    
    for deal_id in range(1, 4):
        initial_state = create_test_state(deal_id)
        
        print(f"\nDeal {deal_id}:")
        print("-" * 70)
        
        # BFS Old
        print("  BFS (Full Recompute)...", end=" ", flush=True)
        result = bfs_full_recompute(initial_state)
        print(f"{result.runtime_ms:.1f}ms | {result.hash_computations} hashes")
        results.append(result)
        
        # BFS New
        print("  BFS (Incremental)....", end=" ", flush=True)
        result = bfs_incremental_update(initial_state)
        print(f"{result.runtime_ms:.1f}ms | {result.hash_computations} hashes")
        results.append(result)
        
        # DFS Old
        print("  DFS (Full Recompute)...", end=" ", flush=True)
        result = dfs_full_recompute(initial_state)
        print(f"{result.runtime_ms:.1f}ms | {result.hash_computations} hashes")
        results.append(result)
        
        # DFS New
        print("  DFS (Incremental)....", end=" ", flush=True)
        result = dfs_incremental_update(initial_state)
        print(f"{result.runtime_ms:.1f}ms | {result.hash_computations} hashes")
        results.append(result)
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY & ANALYSIS")
    print("="*70)
    
    bfs_old = [r for r in results if r.algorithm == "BFS" and r.method == "Full Recompute (Old)"]
    bfs_new = [r for r in results if r.algorithm == "BFS" and r.method == "Incremental Update (New)"]
    dfs_old = [r for r in results if r.algorithm == "DFS" and r.method == "Full Recompute (Old)"]
    dfs_new = [r for r in results if r.algorithm == "DFS" and r.method == "Incremental Update (New)"]
    
    if bfs_old and bfs_new:
        avg_old = sum(r.runtime_ms for r in bfs_old) / len(bfs_old)
        avg_new = sum(r.runtime_ms for r in bfs_new) / len(bfs_new)
        speedup = avg_old / avg_new if avg_new > 0 else 0
        
        print(f"\nBFS Performance:")
        print(f"  Full Recompute: {avg_old:.1f}ms (avg)")
        print(f"  Incremental:    {avg_new:.1f}ms (avg)")
        print(f"  Speedup:        {speedup:.2f}x faster with incremental")
        
        hash_ops_old = sum(r.hash_computations for r in bfs_old) / len(bfs_old)
        hash_ops_new = sum(r.hash_computations for r in bfs_new) / len(bfs_new)
        print(f"  Hash ops (old): {hash_ops_old:.0f}")
        print(f"  Hash ops (new): {hash_ops_new:.0f}")
        print(f"  Reduction:      {(1 - hash_ops_new/hash_ops_old)*100:.1f}% fewer hash ops")
    
    if dfs_old and dfs_new:
        avg_old = sum(r.runtime_ms for r in dfs_old) / len(dfs_old)
        avg_new = sum(r.runtime_ms for r in dfs_new) / len(dfs_new)
        speedup = avg_old / avg_new if avg_new > 0 else 0
        
        print(f"\nDFS Performance:")
        print(f"  Full Recompute: {avg_old:.1f}ms (avg)")
        print(f"  Incremental:    {avg_new:.1f}ms (avg)")
        print(f"  Speedup:        {speedup:.2f}x faster with incremental")
        
        hash_ops_old = sum(r.hash_computations for r in dfs_old) / len(dfs_old)
        hash_ops_new = sum(r.hash_computations for r in dfs_new) / len(dfs_new)
        print(f"  Hash ops (old): {hash_ops_old:.0f}")
        print(f"  Hash ops (new): {hash_ops_new:.0f}")
        print(f"  Reduction:      {(1 - hash_ops_new/hash_ops_old)*100:.1f}% fewer hash ops")
    
    # Save results
    results_path = Path(__file__).parent / "incremental_update_benchmark.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    
    print(f"\nResults saved to: {results_path}")
    print("\n" + "="*70)


if __name__ == "__main__":
    main()
