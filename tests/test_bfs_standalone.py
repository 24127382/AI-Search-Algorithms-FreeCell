"""Standalone BFS solver test without frontend."""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.engine.shuffle import deal_by_game_number
from backend.model.state import State
from backend.solver.algorithms import SearchAlgorithm


def build_initial_state(deal_number: int) -> State:
    """Create initial game state from deal number."""
    tableau = deal_by_game_number(deal_number)
    return State.from_lists(
        tableau=tableau,
        freecells=[None] * 4,
        foundations=[[] for _ in range(4)]
    )


def test_bfs_basic():
    """Test BFS on a simple deal."""
    print("\n" + "="*60)
    print("TEST 1: BFS Basic Solve")
    print("="*60)
    
    deal_num = 1
    state = build_initial_state(deal_num)
    
    print(f"Testing with Deal #{deal_num}")
    print(f"Initial state: {state}")
    
    searcher = SearchAlgorithm(state)
    
    start_time = time.perf_counter()
    path = searcher.search("BFS")
    elapsed = time.perf_counter() - start_time
    
    print(f"\nResult:")
    print(f"  Path returned: {path}")
    print(f"  Path type: {type(path)}")
    if path:
        print(f"  Path length: {len(path)} moves")
    print(f"  Time elapsed: {elapsed:.2f}s")
    
    return path, elapsed


def test_bfs_multiple_deals():
    """Test BFS on multiple deals."""
    print("\n" + "="*60)
    print("TEST 2: BFS on Multiple Deals")
    print("="*60)
    
    test_deals = [1, 2, 3, 4, 5]
    results = {}
    
    for deal_num in test_deals:
        print(f"\nDeal #{deal_num}...", end=" ", flush=True)
        
        state = build_initial_state(deal_num)
        searcher = SearchAlgorithm(state)
        
        start_time = time.perf_counter()
        path = searcher.search("BFS")
        elapsed = time.perf_counter() - start_time
        
        results[deal_num] = {
            "path": path,
            "moves": len(path) if path else 0,
            "time": elapsed,
            "solvable": path is not None
        }
        
        status = "✓ SOLVED" if path else "✗ FAILED"
        print(f"{status} ({elapsed:.2f}s)")
    
    print("\n" + "-"*60)
    print("Summary:")
    print("-"*60)
    for deal_num, result in results.items():
        moves = result["moves"]
        time_taken = result["time"]
        status = "✓" if result["solvable"] else "✗"
        print(f"  Deal {deal_num:3d}: {status} {time_taken:6.2f}s - {moves:3d} moves")
    
    return results


def test_bfs_performance():
    """Measure BFS performance and compare with other algorithms."""
    print("\n" + "="*60)
    print("TEST 3: Algorithm Performance Comparison")
    print("="*60)
    
    deal_num = 1
    state = build_initial_state(deal_num)
    
    algorithms = ["BFS", "DFS"]  # Skip UCS (too slow)
    results = {}
    
    for algo in algorithms:
        print(f"\nTesting {algo}...", end=" ", flush=True)
        searcher = SearchAlgorithm(state)
        
        start_time = time.perf_counter()
        try:
            path = searcher.search(algo)
            elapsed = time.perf_counter() - start_time
            
            results[algo] = {
                "path": path,
                "moves": len(path) if path else 0,
                "time": elapsed,
                "success": path is not None
            }
            
            status = "✓" if path else "✗"
            print(f"{status} ({elapsed:.2f}s)")
        except Exception as e:
            print(f"✗ ERROR: {e}")
            results[algo] = {
                "error": str(e),
                "success": False
            }
    
    print("\n" + "-"*60)
    print("Performance Comparison:")
    print("-"*60)
    for algo, result in results.items():
        if result.get("success"):
            print(f"  {algo:4s}: {result['time']:6.2f}s - {result['moves']:3d} moves")
        else:
            print(f"  {algo:4s}: {result.get('error', 'FAILED')}")
    
    return results


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " BFS STANDALONE TEST SUITE ".center(58) + "║")
    print("╚" + "="*58 + "╝")
    
    try:
        # Run tests
        test_bfs_basic()
        test_bfs_multiple_deals()
        test_bfs_performance()
        
        print("\n" + "="*60)
        print("All tests completed!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
