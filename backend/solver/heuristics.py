"""
heuristics.py

Heuristic functions for A* search in FreeCell.
All heuristics here are admissible and consistent (monotone).
"""

from model.models import State, VALID_RANK


def foundation_distance(state: State) -> int:
    """
    h3 — Primary heuristic. Counts cards not yet on any foundation.

    Each unplaced card requires at least 1 move to reach the foundation,
    so this never overestimates. Also consistent: one move places at most
    one card, so h drops by at most 1 per step.

    Returns: int in range [0, 52]. 0 means solved.
    """
    placed = sum(len(foundation) for foundation in state.foundations)
    return 52 - placed


def buried_cards(state: State) -> int:
    """
    h2 — Supplementary heuristic. Counts cards in the tableau that have
    at least one card on top of them, meaning they cannot move yet.

    Admissible but weaker than foundation_distance for most states.
    Safe to use as max(foundation_distance, buried_cards).
    """
    count = 0
    for column in state.tableau:
        # Every card except the top one is buried
        count += max(0, len(column) - 1)
    return count


def combined_heuristic(state: State) -> int:
    """
    Recommended for A*. Takes the max of h2 and h3.

    max() is always admissible when both components are admissible,
    and produces a tighter (better-informed) bound than either alone.
    """
    return max(foundation_distance(state), buried_cards(state))
