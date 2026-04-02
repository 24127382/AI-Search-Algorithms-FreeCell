"""Heuristic helpers for informed search algorithms."""

from backend.model.card import VALID_RANK
from backend.model.state import State


def zero_heuristic(_state) -> int:
    """Return zero heuristic value.

    Args:
            _state: Unused state argument kept for heuristic signature compatibility.

    Returns:
            int: Always `0`.
    """
    return 0


def cards_remaining_heuristic(state) -> int:
    """Estimate remaining distance by counting non-foundation cards.

    Args:
            state: Current board state.

    Returns:
            int: Number of cards not yet placed in foundations.
    """
    foundation_cards = sum(len(stack) for stack in state.foundations)
    return 52 - foundation_cards


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
    return max(foundation_distance(state), buried_cards(state))
