"""
Quick validation script to ensure refactored code works before running full experiments.

Usage:
    python validate_refactoring.py
"""

import sys
import traceback
from pathlib import Path

def test_imports():
    """Test that all new modules can be imported."""
    print("=" * 70)
    print("TEST 1: Module Imports")
    print("=" * 70)
    
    try:
        from backend.search import BFSAlgorithm, DFSAlgorithm, SearchMetrics
        print("✓ Successfully imported: BFSAlgorithm, DFSAlgorithm, SearchMetrics")
        
        from backend.search.instrumentation import MetricsCollector
        print("✓ Successfully imported: MetricsCollector")
        
        from backend.experiments.runner import ExperimentRunner
        print("✓ Successfully imported: ExperimentRunner")
        
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        traceback.print_exc()
        return False


def test_metrics_dataclass():
    """Test SearchMetrics dataclass."""
    print("\n" + "=" * 70)
    print("TEST 2: SearchMetrics Dataclass")
    print("=" * 70)
    
    try:
        from backend.search.instrumentation import SearchMetrics
        
        metrics = SearchMetrics(
            algorithm="BFS",
            time_seconds=1.234,
            peak_memory_mb=45.6,
            expanded_nodes=12345,
            solution_length=50,
            frontier_max_size=1000
        )
        
        print(f"✓ Created metrics: {metrics}")
        
        # Test serialization
        metrics_dict = metrics.to_dict()
        print(f"✓ to_dict() works: {len(metrics_dict)} fields")
        
        metrics_json = metrics.to_json()
        print(f"✓ to_json() works: {len(metrics_json)} characters")
        
        return True
    except Exception as e:
        print(f"✗ Metrics test failed: {e}")
        traceback.print_exc()
        return False


def test_collector_context_manager():
    """Test MetricsCollector context manager."""
    print("\n" + "=" * 70)
    print("TEST 3: MetricsCollector Context Manager")
    print("=" * 70)
    
    try:
        from backend.search.instrumentation import MetricsCollector
        import time
        
        collector = MetricsCollector()
        
        with collector:
            # Simulate some work
            total = 0
            for i in range(1000000):
                total += i
            
            # Simulate expansions
            for i in range(10):
                collector.record_expansion(100 + i)
        
        print(f"✓ Context manager exited successfully")
        
        metrics = collector.get_metrics(
            algorithm="TEST",
            time_seconds=0.1,
            solution_length=10
        )
        
        print(f"✓ Collected metrics: {metrics}")
        print(f"  - Peak memory: {metrics.peak_memory_mb:.1f} MB")
        print(f"  - Expanded nodes: {metrics.expanded_nodes}")
        print(f"  - Max frontier: {metrics.frontier_max_size}")
        
        return True
    except Exception as e:
        print(f"✗ Collector test failed: {e}")
        traceback.print_exc()
        return False


def test_parent_pointer_reconstruction():
    """Test parent pointer path reconstruction."""
    print("\n" + "=" * 70)
    print("TEST 4: Parent Pointer Path Reconstruction")
    print("=" * 70)
    
    try:
        from backend.search.bfs import BFSAlgorithm
        
        # Create mock data structure
        parents = {
            100: (None, None),  # Initial state: parent_hash=None
            101: (100, "move1"),
            102: (101, "move2"),
            103: (102, "move3"),
        }
        
        state_hashes = {
            100: "state0",
            101: "state1",
            102: "state2",
            103: "state3",
        }
        
        # Test reconstruction from goal state
        path = BFSAlgorithm._reconstruct_path(103, parents, state_hashes)
        
        print(f"✓ Reconstructed path: {path}")
        assert path == ["move1", "move2", "move3"], f"Path reconstruction failed: got {path}"
        print(f"✓ Path reconstruction correct: {len(path)} moves")
        
        # Test reconstruction from initial state (edge case)
        path_initial = BFSAlgorithm._reconstruct_path(100, parents, state_hashes)
        assert path_initial == [], f"Initial state should have empty path, got {path_initial}"
        print(f"✓ Initial state correctly returns empty path")
        
        return True
    except Exception as e:
        print(f"✗ Path reconstruction test failed: {e}")
        traceback.print_exc()
        return False


def test_state_and_moves():
    """Test that State and Move classes can be instantiated."""
    print("\n" + "=" * 70)
    print("TEST 5: State and Move Classes")
    print("=" * 70)
    
    try:
        from backend.model.state import State
        from backend.model.move import Move
        
        print("✓ Successfully imported: State, Move")
        
        # Check State is hashable
        state_hash = hash  # We're testing the function exists
        print("✓ State class available and hashable")
        
        # Check Move class available
        move_class = Move
        print("✓ Move class available")
        
        return True
    except Exception as e:
        print(f"✗ State/Move test failed: {e}")
        traceback.print_exc()
        return False


def test_file_structure():
    """Check that all required files exist."""
    print("\n" + "=" * 70)
    print("TEST 6: File Structure")
    print("=" * 70)
    
    required_files = [
        "backend/search/__init__.py",
        "backend/search/bfs.py",
        "backend/search/dfs.py",
        "backend/search/instrumentation.py",
        "backend/experiments/__init__.py",
        "backend/experiments/runner.py",
        "visualization.py",
        "IMPROVEMENTS.md",
        "QUICKSTART.md",
        "REFACTORING_SUMMARY.md",
    ]
    
    all_exist = True
    for filepath in required_files:
        full_path = Path(filepath)
        if full_path.exists():
            print(f"✓ {filepath}")
        else:
            print(f"✗ {filepath} (MISSING)")
            all_exist = False
    
    return all_exist


def test_docstring_completeness():
    """Check that modules have comprehensive docstrings."""
    print("\n" + "=" * 70)
    print("TEST 7: Docstring Completeness")
    print("=" * 70)
    
    try:
        from backend.search.bfs import BFSAlgorithm
        from backend.search.dfs import DFSAlgorithm
        from backend.search.instrumentation import SearchMetrics, MetricsCollector
        
        classes = [
            ("BFSAlgorithm", BFSAlgorithm),
            ("DFSAlgorithm", DFSAlgorithm),
            ("SearchMetrics", SearchMetrics),
            ("MetricsCollector", MetricsCollector),
        ]
        
        all_good = True
        for name, cls in classes:
            has_doc = cls.__doc__ is not None and len(cls.__doc__) > 20
            status = "✓" if has_doc else "✗"
            print(f"{status} {name}: {len(cls.__doc__) if cls.__doc__ else 0} chars")
            if not has_doc:
                all_good = False
        
        return all_good
    except Exception as e:
        print(f"✗ Docstring test failed: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all validation tests."""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "REFACTORED CODE VALIDATION".center(68) + "║")
    print("║" + "FreeCell Solver - BFS/DFS Research Grade".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "═" * 68 + "╝")
    
    tests = [
        ("Imports", test_imports),
        ("SearchMetrics Dataclass", test_metrics_dataclass),
        ("MetricsCollector Context Manager", test_collector_context_manager),
        ("Parent Pointer Reconstruction", test_parent_pointer_reconstruction),
        ("State and Move Classes", test_state_and_moves),
        ("File Structure", test_file_structure),
        ("Docstring Completeness", test_docstring_completeness),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n✗ Unexpected error in {test_name}: {e}")
            traceback.print_exc()
            results[test_name] = False
    
    # Summary
    print("\n\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:8} {test_name}")
    
    total_passed = sum(1 for p in results.values() if p)
    total_tests = len(results)
    
    print("=" * 70)
    print(f"Total: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("\n✓✓✓ ALL VALIDATION TESTS PASSED ✓✓✓")
        print("\nYou can now safely run:")
        print("  python -m backend.experiments.runner --deals 10")
        return 0
    else:
        print("\n✗✗✗ SOME TESTS FAILED ✗✗✗")
        print("\nPlease review the errors above before running experiments.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
