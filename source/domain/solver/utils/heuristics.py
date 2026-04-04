"""Heuristic helpers for informed search algorithms."""

from source.domain.model.card import VALID_RANK
from source.domain.model.state import State
from source.domain.solver.utils.utility import env_int

_UCS_FOUNDATION_MOVE_COST_FOR_HEURISTIC = env_int(
    "UCS_FOUNDATION_MOVE_COST", -19, minimum=-10000
)


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
    """Default admissible-ish heuristic in move-count space."""
    return max(foundation_distance(state), buried_cards(state))


def occupied_freecells(state: State) -> int:
    """Count currently occupied freecells."""
    return sum(1 for cell in state.freecells if cell is not None)


def progress_pressure_heuristic(state: State) -> int:
    """Aggressive heuristic favoring progress and board mobility.

    This is intentionally more informed but can be inadmissible.
    """
    return (
        foundation_distance(state)
        + (buried_cards(state) // 2)
        + occupied_freecells(state)
    )


def foundation_cost_lower_bound(state: State) -> int:
    """Cost-aware lower bound for negative foundation edge models.

    If foundation moves carry negative cost, each remaining card can at best
    contribute one such move, producing a valid (very loose) cost lower bound.
    """
    return foundation_distance(state) * _UCS_FOUNDATION_MOVE_COST_FOR_HEURISTIC
