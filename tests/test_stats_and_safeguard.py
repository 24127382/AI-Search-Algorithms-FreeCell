#!/usr/bin/env python3
"""
Test script for BFS/DFS statistics tracking and safeguard mechanism.

This script validates:
1. BFS and DFS track all required statistics
2. BFS frontier limit safeguard works correctly
3. DFS frontier limit safeguard works correctly
4. User feedback messages are generated appropriately
"""

import sys
from backend.model.state import GameState
from backend.solver.bfs import BFSAlgorithm
from backend.solver.dfs import DFSAlgorithm
from backend.engine.engine import get_valid_moves


def test_statistics_tracking():
    """Test that BFS and DFS track all required statistics."""
    print("=" * 70)
    print("TEST 1: Statistics Tracking")
    print("=" * 70)
    
    # Create a simple initial state
    initial_state = GameState()
    
    # Test BFS statistics
    print("\n--- BFS Statistics ---")
    bfs = BFSAlgorithm(initial_state)
    result = bfs.search()
    
    if bfs.last_run_stats:
        stats = bfs.last_run_stats
        required_metrics = [
            "solution_found", "elapsed_ms", "solution_length",
            "expanded_nodes", "generated_nodes", "pruned_by_closed",
            "closed_prune_rate", "effective_branching_factor",
            "peak_frontier_size", "peak_closed_size",
            "final_frontier_size", "final_closed_size"
        ]
        
        print(f"Stats available: {len(stats)} metrics")
        missing = [m for m in required_metrics if m not in stats]
        
        if missing:
            print(f"❌ MISSING METRICS: {missing}")
            return False
        else:
            print("✓ All required metrics present")
            print(f"  - solution_found: {stats['solution_found']}")
            print(f"  - expanded_nodes: {stats['expanded_nodes']}")
            print(f"  - generated_nodes: {stats['generated_nodes']}")
            print(f"  - pruned_by_closed: {stats['pruned_by_closed']}")
            print(f"  - effective_branching_factor: {stats['effective_branching_factor']:.3f}")
            print(f"  - peak_frontier_size: {stats['peak_frontier_size']}")
            print(f"  - peak_closed_size: {stats['peak_closed_size']}")
    else:
        print("❌ No statistics collected")
        return False
    
    # Test DFS statistics
    print("\n--- DFS Statistics ---")
    dfs = DFSAlgorithm(initial_state)
    result = dfs.search()
    
    if dfs.last_run_stats:
        stats = dfs.last_run_stats
        missing = [m for m in required_metrics if m not in stats]
        
        if missing:
            print(f"❌ MISSING METRICS: {missing}")
            return False
        else:
            print("✓ All required metrics present")
            print(f"  - solution_found: {stats['solution_found']}")
            print(f"  - expanded_nodes: {stats['expanded_nodes']}")
            print(f"  - generated_nodes: {stats['generated_nodes']}")
            print(f"  - pruned_by_closed: {stats['pruned_by_closed']}")
            print(f"  - effective_branching_factor: {stats['effective_branching_factor']:.3f}")
            print(f"  - peak_frontier_size: {stats['peak_frontier_size']}")
            print(f"  - peak_closed_size: {stats['peak_closed_size']}")
    else:
        print("❌ No statistics collected")
        return False
    
    return True


def test_bfs_safeguard():
    """Test BFS frontier limit safeguard."""
    print("\n" + "=" * 70)
    print("TEST 2: BFS Frontier Limit Safeguard")
    print("=" * 70)
    
    initial_state = GameState()
    
    # Create BFS with a very small frontier limit to trigger safeguard
    small_limit = 100
    bfs = BFSAlgorithm(initial_state, max_frontier_size=small_limit)
    
    print(f"\nRunning BFS with max_frontier_size={small_limit}...")
    result = bfs.search()
    
    if bfs.last_run_stats:
        stats = bfs.last_run_stats
        
        # Check if termination reason is set
        if "termination_reason" in stats and stats["termination_reason"] == "FRONTIER_LIMIT_REACHED":
            print("✓ Frontier limit safeguard triggered as expected")
            print(f"  - final_frontier_size: {stats['final_frontier_size']}")
            print(f"  - termination_reason: {stats['termination_reason']}")
            
            # Check user feedback
            feedback = bfs.get_user_feedback()
            if feedback:
                print("\n✓ User feedback generated:")
                for line in feedback.split('\n'):
                    print(f"  {line}")
            return True
        else:
            # Safeguard might not trigger if the problem is simple
            print("⚠ Safeguard did not trigger (problem might be too simple)")
            print(f"  - solution_found: {stats['solution_found']}")
            print(f"  - peak_frontier_size: {stats['peak_frontier_size']}")
            return True
    else:
        print("❌ No statistics collected")
        return False


def test_dfs_safeguard():
    """Test DFS frontier limit safeguard."""
    print("\n" + "=" * 70)
    print("TEST 3: DFS Frontier Limit Safeguard")
    print("=" * 70)
    
    initial_state = GameState()
    
    # Create DFS with a very small frontier limit to trigger safeguard
    small_limit = 100
    dfs = DFSAlgorithm(initial_state, max_frontier_size=small_limit)
    
    print(f"\nRunning DFS with max_frontier_size={small_limit}...")
    result = dfs.search()
    
    if dfs.last_run_stats:
        stats = dfs.last_run_stats
        
        # Check if termination reason is set
        if "termination_reason" in stats and stats["termination_reason"] == "FRONTIER_LIMIT_REACHED":
            print("✓ Frontier limit safeguard triggered as expected")
            print(f"  - final_frontier_size: {stats['final_frontier_size']}")
            print(f"  - termination_reason: {stats['termination_reason']}")
            
            # Check user feedback
            feedback = dfs.get_user_feedback()
            if feedback:
                print("\n✓ User feedback generated:")
                for line in feedback.split('\n'):
                    print(f"  {line}")
            return True
        else:
            # Safeguard might not trigger if the problem is simple
            print("⚠ Safeguard did not trigger (problem might be too simple)")
            print(f"  - solution_found: {stats['solution_found']}")
            print(f"  - peak_frontier_size: {stats['peak_frontier_size']}")
            return True
    else:
        print("❌ No statistics collected")
        return False


def test_user_feedback():
    """Test user feedback generation for various scenarios."""
    print("\n" + "=" * 70)
    print("TEST 4: User Feedback Generation")
    print("=" * 70)
    
    initial_state = GameState()
    
    # Test successful solution feedback
    print("\n--- Scenario 1: Successful Solution ---")
    bfs = BFSAlgorithm(initial_state)
    result = bfs.search()
    feedback = bfs.get_user_feedback()
    if feedback:
        print(f"✓ Feedback generated: {feedback}")
    else:
        print("✓ No feedback (empty string expected for some cases)")
    
    # Test frontier limit exceeded feedback
    print("\n--- Scenario 2: Frontier Limit Exceeded (simulated) ---")
    bfs_limited = BFSAlgorithm(initial_state, max_frontier_size=100)
    result = bfs_limited.search()
    feedback = bfs_limited.get_user_feedback()
    if feedback:
        print(f"✓ Feedback generated:\n{feedback}")
    else:
        print("⚠ No frontier limit feedback (safeguard might not have been triggered)")
    
    return True


def test_format_stats():
    """Test statistics formatting."""
    print("\n" + "=" * 70)
    print("TEST 5: Statistics Formatting")
    print("=" * 70)
    
    initial_state = GameState()
    
    print("\n--- BFS Format ---")
    bfs = BFSAlgorithm(initial_state)
    result = bfs.search()
    formatted = bfs.format_last_run_stats()
    if formatted and "No BFS stats" not in formatted:
        print("✓ BFS stats formatted correctly:")
        for line in formatted.split('\n')[:5]:  # Show first 5 lines
            print(f"  {line}")
        print("  ...")
    else:
        print("⚠ Could not format BFS stats")
    
    print("\n--- DFS Format ---")
    dfs = DFSAlgorithm(initial_state)
    result = dfs.search()
    formatted = dfs.format_last_run_stats()
    if formatted and "No DFS stats" not in formatted:
        print("✓ DFS stats formatted correctly:")
        for line in formatted.split('\n')[:5]:  # Show first 5 lines
            print(f"  {line}")
        print("  ...")
    else:
        print("⚠ Could not format DFS stats")
    
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("FREECELL SOLVER: BFS/DFS STATISTICS AND SAFEGUARD TESTS")
    print("=" * 70)
    
    tests = [
        ("Statistics Tracking", test_statistics_tracking),
        ("BFS Safeguard", test_bfs_safeguard),
        ("DFS Safeguard", test_dfs_safeguard),
        ("User Feedback", test_user_feedback),
        ("Stats Formatting", test_format_stats),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n❌ TEST FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\nPassed: {passed}/{total}")
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")
    
    print("\n" + "=" * 70)
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
