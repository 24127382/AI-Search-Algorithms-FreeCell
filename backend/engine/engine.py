"""Core move generation and state transition utilities for FreeCell search."""

from typing import List, Optional, Tuple
from backend.model.move import Move, MoveType
from backend.model.state import State
from backend.rule.rules import (
    can_move_to_foundation,
    find_valid_destinations,
    get_max_sequence_length,
    get_movable_sequences,
    is_safe_to_foundation,
)


def _auto_foundation_priority(move: Move) -> tuple[int, int, int, int]:
    """Build a deterministic sort key for safe foundation candidates.

    Args:
        move: Candidate move that sends one card to a foundation.

    Returns:
        Tuple[int, int, int, int]: Priority key used by `min`.
    """
    from_type_priority = 0 if move.from_pos[0] == 'freecell' else 1
    return (move.card.rank_val, from_type_priority, move.from_pos[1], move.to_pos[1])


def _move_priority(move: Move) -> tuple[int, int, int, int, int]:
    """Build a deterministic sort key for move ordering.

    Args:
        move: Candidate legal move.

    Returns:
        Tuple[int, int, int, int, int]: Priority key where smaller means earlier.
    """
    sequence_len = len(move.sequence) if move.sequence else 1
    if move.to_pos[0] == 'foundation':
        group = 0
    elif move.from_pos[0] == 'freecell' and move.to_pos[0] == 'tableau':
        group = 1
    elif move.to_pos[0] == 'tableau' and sequence_len > 1:
        group = 2
    elif move.to_pos[0] == 'tableau':
        group = 3
    else:
        group = 4

    return (group, -sequence_len, move.from_pos[1], move.to_pos[1], -move.card.rank_val)


def _is_immediate_undo(candidate: Move, last_move: Optional[Move]) -> bool:
    """Check whether a move immediately undoes the previous move.

    Args:
        candidate: Move being considered.
        last_move: Previously applied move, if any.

    Returns:
        bool: `True` when candidate is a direct single-card reverse move.
    """
    if last_move is None:
        return False
    if candidate.from_pos != last_move.to_pos or candidate.to_pos != last_move.from_pos:
        return False
    candidate_len = len(candidate.sequence) if candidate.sequence else 1
    last_len = len(last_move.sequence) if last_move.sequence else 1
    if candidate_len != 1 or last_len != 1:
        return False
    if candidate.to_pos[0] == 'foundation' or candidate.from_pos[0] == 'foundation':
        return False
    return candidate.card == last_move.card


def _safe_foundation_move_from_tableau(state: State, col_idx: int) -> Optional[Move]:
    """Build a safe tableau-to-foundation move for one column.

    Args:
        state: Current board state.
        col_idx: Source tableau column index.

    Returns:
        Optional[Move]: Safe legal move, or `None` when unavailable.
    """
    column = state.tableau[col_idx]
    if not column:
        return None

    card = column[-1]
    f_idx = card.suit_idx
    if not can_move_to_foundation(card, state.foundations[f_idx], f_idx):
        return None
    if not is_safe_to_foundation(state, card):
        return None

    return Move(
        MoveType.TABLEAU_TO_FOUNDATION,
        card,
        ('tableau', col_idx),
        ('foundation', f_idx),
        sequence=(card,),
    )


def _safe_foundation_move_from_freecell(state: State, cell_idx: int) -> Optional[Move]:
    """Build a safe freecell-to-foundation move for one freecell.

    Args:
        state: Current board state.
        cell_idx: Source freecell index.

    Returns:
        Optional[Move]: Safe legal move, or `None` when unavailable.
    """
    card = state.freecells[cell_idx]
    if card is None:
        return None

    f_idx = card.suit_idx
    if not can_move_to_foundation(card, state.foundations[f_idx], f_idx):
        return None
    if not is_safe_to_foundation(state, card):
        return None

    return Move(
        MoveType.FREECELL_TO_FOUNDATION,
        card,
        ('freecell', cell_idx),
        ('foundation', f_idx),
        sequence=(card,),
    )


def _find_forced_foundation_move(state: State) -> Optional[Move]:
    """Select one deterministic safe move to foundation when possible.

    Args:
        state: Current board state.

    Returns:
        Optional[Move]: Chosen safe move, or `None` if no safe move exists.
    """
    candidates = []

    for col_idx in range(len(state.tableau)):
        move = _safe_foundation_move_from_tableau(state, col_idx)
        if move is not None:
            candidates.append(move)

    for cell_idx in range(len(state.freecells)):
        move = _safe_foundation_move_from_freecell(state, cell_idx)
        if move is not None:
            candidates.append(move)

    if not candidates:
        return None
    return min(candidates, key=_auto_foundation_priority)


def apply_forced_foundation_closure(state: State) -> tuple[State, Tuple[Move, ...]]:
    """Apply all consecutive forced safe-foundation moves.

    Args:
        state: State to start closure from.

    Returns:
        tuple[State, Tuple[Move, ...]]: Final state and moves applied during closure.
    """
    current_state = state
    forced_moves: list[Move] = []

    while True:
        forced_move = _find_forced_foundation_move(current_state)
        if forced_move is None:
            break
        current_state = _apply_single_move(current_state, forced_move)
        forced_moves.append(forced_move)

    return current_state, tuple(forced_moves)


def get_valid_moves(state: State, prune_safe: bool = True, last_move: Optional[Move] = None) -> List[Move]:
    """Generate legal moves for the current state.

    Args:
        state: Current board state.
        prune_safe: Whether to collapse safe-foundation branches to one move.
        last_move: Optional previous move used to prune immediate undo actions.

    Returns:
        List[Move]: Deterministically ordered legal moves.
    """
    moves = []

    max_seq_len = get_max_sequence_length(state)

    for col_idx, column in enumerate(state.tableau):
        sequences = get_movable_sequences(column)
        for sequence in sequences:
            if len(sequence) <= max_seq_len:
                destinations = find_valid_destinations(state, sequence, ('tableau', col_idx), max_seq_len)
                moves.extend(destinations)

    for cell_idx, card in enumerate(state.freecells):
        if card is not None:
            destinations = find_valid_destinations(state, [card], ('freecell', cell_idx), max_seq_len)
            moves.extend(destinations)

    # Auto-move pruning: if any move to foundation is "safe", choose a single
    # deterministic dominant move so the solver does not branch at this state.
    if prune_safe:
        forced_move = _find_forced_foundation_move(state)
        if forced_move is not None:
            return [forced_move]

    if last_move is not None:
        moves = [move for move in moves if not _is_immediate_undo(move, last_move)]

    moves.sort(key=_move_priority)
    return moves


def _apply_single_move(state: State, move: Move) -> State:
    """Apply one validated move and return a new immutable state.

    Args:
        state: Source state.
        move: Legal move to apply.

    Returns:
        State: Next state after applying the move.

    Raises:
        ValueError: If tableau move sequence metadata is missing or inconsistent.
    """
    new_tableau = [list(col) for col in state.tableau]
    new_freecells = list(state.freecells)
    new_foundations = [list(f) for f in state.foundations]

    from_type, from_idx = move.from_pos
    to_type, to_idx = move.to_pos
    touched_tableau_indices = set()

    moving_cards = list(move.sequence) if move.sequence else [move.card]

    if from_type == 'tableau':
        if not move.sequence:
            raise ValueError("Tableau moves must include move.sequence to avoid ambiguous state transitions")

        col = new_tableau[from_idx]
        n = len(move.sequence)
        moving_cards = col[-n:]
        if tuple(moving_cards) != move.sequence:
            raise ValueError("move.sequence does not match source tableau top sequence")
        new_tableau[from_idx] = col[:-n]
        touched_tableau_indices.add(from_idx)
    elif from_type == 'freecell':
        new_freecells[from_idx] = None

    if to_type == 'tableau':
        new_tableau[to_idx].extend(moving_cards)
        touched_tableau_indices.add(to_idx)
    elif to_type == 'freecell':
        new_freecells[to_idx] = moving_cards[0]
    elif to_type == 'foundation':
        new_foundations[to_idx].append(moving_cards[0])

    return State.from_transition(
        prev_state=state,
        tableau=new_tableau,
        freecells=new_freecells,
        foundations=new_foundations,
        touched_tableau_indices=touched_tableau_indices,
    )

def apply_move(state: State, move: Move, collapse_forced: bool = False) -> State:
    """Apply one move with optional forced-foundation closure.

    Args:
        state: Source state.
        move: Legal move to apply.
        collapse_forced: Whether to apply forced safe-foundation chain after move.

    Returns:
        State: Resulting state.
    """
    next_state = _apply_single_move(state, move)
    if not collapse_forced:
        return next_state
    collapsed_state, _ = apply_forced_foundation_closure(next_state)
    return collapsed_state


def apply_move_with_forced(state: State, move: Move) -> tuple[State, Tuple[Move, ...]]:
    """Apply one move and compute forced-foundation closure.

    Args:
        state: Source state.
        move: Legal move to apply.

    Returns:
        tuple[State, Tuple[Move, ...]]: Result state and forced moves applied.
    """
    next_state = _apply_single_move(state, move)
    return apply_forced_foundation_closure(next_state)
