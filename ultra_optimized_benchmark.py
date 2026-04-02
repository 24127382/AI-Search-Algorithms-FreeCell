"""
Ultra-optimized Zobrist incremental hashing
Maintains single hasher instance per path for maximum efficiency
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
class OptimizedResult:
    """Results from optimized benchmark"""
    test: str
    runtime_ms: float
    nodes_expanded: int
    hash_ops: int
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
    """Extract move details for incremental update"""
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
# ULTRA-OPTIMIZED: Proper incremental with path-based hasher maintenance
# =============================================================================

def bfs_ultra_optimized(initial_state, max_nodes=5000):
    """BFS with properly maintained hasher per search path"""
    zobrist_table = get_zobrist_table()
    start_time = time.perf_counter()
    hash_time = 0
    
    # Initialize root
    root_hasher = ZobristHash(zobrist_table)
    root_hasher.hash_state(initial_state)
    
    queue = deque([(initial_state, [], root_hasher)])
    visited = {root_hasher.get_hash(): True}
    nodes_expanded = 0
    hash_ops = 1  # Initial full hash
    
    while queue and nodes_expanded < max_nodes:
        state, path, state_hasher = queue.popleft()
        nodes_expanded += 1
        
        if state.is_goal:
            elapsed = (time.perf_counter() - start_time) * 1000
            return OptimizedResult(
                test="BFS (Ultra-Optimized)",
                runtime_ms=elapsed,
                nodes_expanded=nodes_expanded,
                hash_ops=hash_ops,
                avg_hash_time_us=hash_time * 1e6 / max(hash_ops, 1)
            )
        
        valid_moves = get_valid_moves(state)
        for move in valid_moves:
            new_state = apply_move(state, move)
            
            # Create hasher for new state by cloning current hasher
            # and applying incremental update
            try:
                new_hasher = ZobristHash(zobrist_table)
                new_hasher.hash_value = state_hasher.hash_value  # Copy hash state
                
                move_details = extract_move_details(state, move, new_state)
                if move_details:
                    card, from_params, to_params = move_details
                    hash_start = time.perf_counter()
                    new_hasher.update_move(card, **from_params, **to_params)
                    hash_time += time.perf_counter() - hash_start
                    hash_ops += 1
                else:
                    # Fallback
                    hash_start = time.perf_counter()
                    new_hasher.hash_state(new_state)
                    hash_time += time.perf_counter() - hash_start
                    hash_ops += 1
            except:
                # Safe fallback
                new_hasher = ZobristHash(zobrist_table)
                hash_start = time.perf_counter()
                new_hasher.hash_state(new_state)
                hash_time += time.perf_counter() - hash_start
                hash_ops += 1
            
            new_hash = new_hasher.get_hash()
            if new_hash not in visited:
                visited[new_hash] = True
                queue.append((new_state, path + [move], new_hasher))
    
    elapsed = (time.perf_counter() - start_time) * 1000
    return OptimizedResult(
        test="BFS (Ultra-Optimized)",
        runtime_ms=elapsed,
        nodes_expanded=nodes_expanded,
        hash_ops=hash_ops,
        avg_hash_time_us=hash_time * 1e6 / max(hash_ops, 1)
    )


def dfs_ultra_optimized(initial_state, max_nodes=5000):
    """DFS with properly maintained hasher per search path"""
    zobrist_table = get_zobrist_table()
    start_time = time.perf_counter()
    hash_time = 0
    
    root_hasher = ZobristHash(zobrist_table)
    root_hasher.hash_state(initial_state)
    
    stack = [(initial_state, [], root_hasher)]
    visited = {root_hasher.get_hash(): True}
    nodes_expanded = 0
    hash_ops = 1
    
    while stack and nodes_expanded < max_nodes:
        state, path, state_hasher = stack.pop()
        nodes_expanded += 1
        
        if state.is_goal:
            elapsed = (time.perf_counter() - start_time) * 1000
            return OptimizedResult(
                test="DFS (Ultra-Optimized)",
                runtime_ms=elapsed,
                nodes_expanded=nodes_expanded,
                hash_ops=hash_ops,
                avg_hash_time_us=hash_time * 1e6 / max(hash_ops, 1)
            )
        
        valid_moves = get_valid_moves(state)
        for move in valid_moves:
            new_state = apply_move(state, move)
            
            try:
                new_hasher = ZobristHash(zobrist_table)
                new_hasher.hash_value = state_hasher.hash_value
                
                move_details = extract_move_details(state, move, new_state)
                if move_details:
                    card, from_params, to_params = move_details
                    hash_start = time.perf_counter()
                    new_hasher.update_move(card, **from_params, **to_params)
                    hash_time += time.perf_counter() - hash_start
                    hash_ops += 1
                else:
                    hash_start = time.perf_counter()
                    new_hasher.hash_state(new_state)
                    hash_time += time.perf_counter() - hash_start
                    hash_ops += 1
            except:
                new_hasher = ZobristHash(zobrist_table)
                hash_start = time.perf_counter()
                new_hasher.hash_state(new_state)
                hash_time += time.perf_counter() - hash_start
                hash_ops += 1
            
            new_hash = new_hasher.get_hash()
            if new_hash not in visited:
                visited[new_hash] = True
                stack.append((new_state, path + [move], new_hasher))
    
    elapsed = (time.perf_counter() - start_time) * 1000
    return OptimizedResult(
        test="DFS (Ultra-Optimized)",
        runtime_ms=elapsed,
        nodes_expanded=nodes_expanded,
        hash_ops=hash_ops,
        avg_hash_time_us=hash_time * 1e6 / max(hash_ops, 1)
    )


def main():
    print("\n" + "="*70)
    print("ULTRA-OPTIMIZED ZOBRIST INCREMENTAL HASHING")
    print("Maintaining hasher state throughout search path")
    print("="*70 + "\n")
    
    results = []
    
    for deal_id in range(1, 4):
        initial_state = create_test_state(deal_id)
        
        print(f"Deal {deal_id}:")
        
        print("  BFS (Ultra-Optimized)...", end=" ", flush=True)
        result = bfs_ultra_optimized(initial_state)
        print(f"{result.runtime_ms:.1f}ms | {result.hash_ops} ops | {result.avg_hash_time_us:.2f} us/op")
        results.append(result)
        
        print("  DFS (Ultra-Optimized)...", end=" ", flush=True)
        result = dfs_ultra_optimized(initial_state)
        print(f"{result.runtime_ms:.1f}ms | {result.hash_ops} ops | {result.avg_hash_time_us:.2f} us/op")
        results.append(result)
    
    # Analysis
    print("\n" + "="*70)
    print("OPTIMIZATION RESULTS")
    print("="*70)
    
    bfs_results = [r for r in results if "BFS" in r.test]
    dfs_results = [r for r in results if "DFS" in r.test]
    
    if bfs_results:
        avg_time = sum(r.runtime_ms for r in bfs_results) / len(bfs_results)
        avg_ops = sum(r.hash_ops for r in bfs_results) / len(bfs_results)
        avg_us = sum(r.avg_hash_time_us for r in bfs_results) / len(bfs_results)
        print(f"\nBFS (Ultra-Optimized):")
        print(f"  Average runtime: {avg_time:.1f}ms")
        print(f"  Average hash ops: {avg_ops:.0f}")
        print(f"  Average hash time: {avg_us:.2f} us/op")
    
    if dfs_results:
        avg_time = sum(r.runtime_ms for r in dfs_results) / len(dfs_results)
        avg_ops = sum(r.hash_ops for r in dfs_results) / len(dfs_results)
        avg_us = sum(r.avg_hash_time_us for r in dfs_results) / len(dfs_results)
        print(f"\nDFS (Ultra-Optimized):")
        print(f"  Average runtime: {avg_time:.1f}ms")
        print(f"  Average hash ops: {avg_ops:.0f}")
        print(f"  Average hash time: {avg_us:.2f} us/op")
    
    # Save
    results_path = Path(__file__).parent / "ultra_optimized_benchmark.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    
    print(f"\nResults saved to: {results_path}\n")
    print("="*70)


if __name__ == "__main__":
    main()
