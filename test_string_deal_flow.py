#!/usr/bin/env python3
"""Test the string deal ID input flow (parsing, generation, display)."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.engine.shuffle import generate_game
from backend.model.state import State
from typing import Union

# Simulate the dialog parsing logic
SPECIAL_TEST_CASE_IDS = {"bfs_easy_10", "bfs_hard_20"}

def parse_deal_input(raw_value: str) -> Union[int, str, None]:
    """Simulate DealNumberDialog._confirm() parsing logic."""
    if not raw_value:
        return None
    
    # Try parsing as integer first
    try:
        return int(raw_value)
    except ValueError:
        pass
    
    # Check if it's a valid special test case ID
    if raw_value.lower() in SPECIAL_TEST_CASE_IDS:
        return raw_value.lower()
    
    raise ValueError(f"Invalid input: '{raw_value}'")

def test_full_flow():
    """Test the complete flow: parse -> generate -> display."""
    print("=" * 70)
    print("TESTING FULL DEAL ID INPUT FLOW")
    print("=" * 70)
    
    test_cases = [
        ("42", "Integer deal"),
        ("bfs_easy_10", "Special easy case"),
        ("BFS_EASY_10", "Special easy case (uppercase)"),
        ("bfs_hard_20", "Special hard case"),
        ("", "Empty (random)"),
    ]
    
    for input_str, description in test_cases:
        print(f"\nTest: {description}")
        print(f"  Input: '{input_str}'")
        
        # Step 1: Parse input (simulating DealNumberDialog)
        try:
            deal_id = parse_deal_input(input_str)
        except ValueError as e:
            print(f"  ✗ Parse failed: {e}")
            return False
        
        print(f"  → Parsed as: {deal_id!r}")
        
        # Step 2: Generate game state
        if deal_id is None:
            # Random deal
            from backend.engine.shuffle import random_deal_number
            deal_id = random_deal_number()
            print(f"  → Using random deal: {deal_id}")
        
        try:
            state = generate_game(deal_id)
        except Exception as e:
            print(f"  ✗ Generate failed: {e}")
            return False
        
        # Verify state
        if not isinstance(state, State):
            print(f"  ✗ State is wrong type: {type(state)}")
            return False
        
        # Count cards
        total = sum(len(col) for col in state.tableau)
        total += sum(1 for fc in state.freecells if fc is not None)
        total += sum(len(col) for col in state.foundations)
        
        if total != 52:
            print(f"  ✗ Card count wrong: {total} (expected 52)")
            return False
        
        # Step 3: Display label (simulating BoardWidget display)
        if isinstance(deal_id, int):
            label = f"Deal #{deal_id}"
        else:
            label = f"Deal: {deal_id}"
        
        print(f"  → Display label: {label}")
        print(f"  ✓ {description} works (52 cards, is_goal={state.is_goal})")
    
    # Test invalid inputs
    print("\nTest: Invalid input handling")
    invalid_inputs = ["invalid_case", "bfs_medium_15", "abc123"]
    
    for input_str in invalid_inputs:
        try:
            deal_id = parse_deal_input(input_str)
            print(f"  ✗ '{input_str}' should have raised ValueError")
            return False
        except ValueError:
            print(f"  ✓ '{input_str}' correctly rejected")
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED!")
    print("=" * 70)
    print("\nThe signal fix (Signal(object)) should now work correctly.")
    print("The application can now accept both int and str deal IDs.")
    return True

if __name__ == "__main__":
    success = test_full_flow()
    sys.exit(0 if success else 1)
