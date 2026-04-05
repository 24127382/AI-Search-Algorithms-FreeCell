#!/usr/bin/env python3
"""Test script to validate unified generate_game interface."""

import sys
from pathlib import Path

# Add parent directory to path so imports work correctly
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.engine.shuffle import generate_game
from backend.model.state import State

def test_generate_game():
    """Test that generate_game works with both int and str inputs."""
    print("=" * 70)
    print("TESTING UNIFIED generate_game() INTERFACE")
    print("=" * 70)
    
    # Test 1: Microsoft deal number (integer)
    print("\n[Test 1] Microsoft deal number (integer)")
    try:
        state_42 = generate_game(42)
        assert isinstance(state_42, State), "Should return State object"
        assert len(state_42.tableau) == 8, "Should have 8 tableau columns"
        assert len(state_42.freecells) == 4, "Should have 4 freecells"
        assert len(state_42.foundations) == 4, "Should have 4 foundations"
        assert not state_42.is_goal, "Deal 42 should not start at goal"
        
        # Count total cards
        total_cards = sum(len(col) for col in state_42.tableau)
        for fc in state_42.freecells:
            if fc is not None:
                total_cards += 1
        for col in state_42.foundations:
            total_cards += len(col)
        assert total_cards == 52, f"Should have 52 cards total, got {total_cards}"
        
        print(f"  ✓ Successfully loaded Microsoft deal 42")
        print(f"    - Tableau: {sum(len(col) for col in state_42.tableau)} cards")
        print(f"    - Foundations: {sum(len(col) for col in state_42.foundations)} cards")
        print(f"    - Is goal: {state_42.is_goal}")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False
    
    # Test 2: Special case - easy (string)
    print("\n[Test 2] Special test case ID 'bfs_easy_10' (string)")
    try:
        state_easy = generate_game("bfs_easy_10")
        assert isinstance(state_easy, State), "Should return State object"
        assert len(state_easy.tableau) == 8, "Should have 8 tableau columns"
        assert not state_easy.is_goal, "Test case should not start at goal"
        
        # Count total cards
        total_cards = sum(len(col) for col in state_easy.tableau)
        for fc in state_easy.freecells:
            if fc is not None:
                total_cards += 1
        for col in state_easy.foundations:
            total_cards += len(col)
        assert total_cards == 52, f"Should have 52 cards total, got {total_cards}"
        
        print(f"  ✓ Successfully loaded special test case 'bfs_easy_10'")
        print(f"    - Tableau: {sum(len(col) for col in state_easy.tableau)} cards")
        print(f"    - Foundations: {sum(len(col) for col in state_easy.foundations)} cards")
        print(f"    - Is goal: {state_easy.is_goal}")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False
    
    # Test 3: Special case - hard (string)
    print("\n[Test 3] Special test case ID 'bfs_hard_20' (string)")
    try:
        state_hard = generate_game("bfs_hard_20")
        assert isinstance(state_hard, State), "Should return State object"
        assert len(state_hard.tableau) == 8, "Should have 8 tableau columns"
        assert not state_hard.is_goal, "Test case should not start at goal"
        
        # Count total cards
        total_cards = sum(len(col) for col in state_hard.tableau)
        for fc in state_hard.freecells:
            if fc is not None:
                total_cards += 1
        for col in state_hard.foundations:
            total_cards += len(col)
        assert total_cards == 52, f"Should have 52 cards total, got {total_cards}"
        
        print(f"  ✓ Successfully loaded special test case 'bfs_hard_20'")
        print(f"    - Tableau: {sum(len(col) for col in state_hard.tableau)} cards")
        print(f"    - Foundations: {sum(len(col) for col in state_hard.foundations)} cards")
        print(f"    - Is goal: {state_hard.is_goal}")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False
    
    # Test 4: Invalid special case ID should raise error
    print("\n[Test 4] Invalid special test case ID (should raise error)")
    try:
        state_invalid = generate_game("invalid_test_case")
        print(f"  ✗ FAILED: Should have raised ValueError for invalid ID")
        return False
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    except Exception as e:
        print(f"  ✗ FAILED with unexpected error: {e}")
        return False
    
    # Test 5: Backward compatibility - existing deal_by_game_number still works
    print("\n[Test 5] Backward compatibility - deal_by_game_number() still works")
    try:
        from backend.engine.shuffle import deal_by_game_number
        tableau = deal_by_game_number(42)
        assert isinstance(tableau, tuple), "Should return tuple"
        assert len(tableau) == 8, "Should have 8 columns"
        print(f"  ✓ deal_by_game_number() still works correctly")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False
    
    # Test 6: Verify different deals return different states
    print("\n[Test 6] Verify different inputs return different states")
    try:
        state1 = generate_game(42)
        state2 = generate_game(43)
        state3 = generate_game("bfs_easy_10")
        
        # Different Microsoft deals should produce different tableaus
        cards_42 = str([str(card) for col in state1.tableau for card in col])
        cards_43 = str([str(card) for col in state2.tableau for card in col])
        cards_easy = str([str(card) for col in state3.tableau for card in col])
        
        assert cards_42 != cards_43, "Deal 42 and 43 should be different"
        assert cards_42 != cards_easy, "Microsoft deal and special case should be different"
        
        print(f"  ✓ Different inputs produce different states")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED!")
    print("=" * 70)
    return True

if __name__ == "__main__":
    import sys
    success = test_generate_game()
    sys.exit(0 if success else 1)
