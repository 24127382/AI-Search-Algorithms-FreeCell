"""Core FreeCell engine: move generation, transition, and goal checks."""

from typing import List

from backend.model.models import Move, State
from backend.rule.rules import find_valid_destinations, get_max_sequence_length, get_movable_sequences, is_safe_to_foundation

def get_valid_moves(state: State, prune_safe: bool = True) -> List[Move]:
    """Return all legal moves from the current state."""
    moves = []

    max_seq_len = get_max_sequence_length(state)

    for col_idx, column in enumerate(state.tableau):
        sequences = get_movable_sequences(column)
        for sequence in sequences:
            if len(sequence) <= max_seq_len:
                destinations = find_valid_destinations(state, sequence, ('tableau', col_idx))
                moves.extend(destinations)

    for cell_idx, card in enumerate(state.freecells):
        if card is not None:
            destinations = find_valid_destinations(state, [card], ('freecell', cell_idx))
            moves.extend(destinations)

    if prune_safe:
        for move in moves:
            if move.to_pos[0] == 'foundation' and is_safe_to_foundation(state, move.card):
                return [move]

    return moves

def apply_move(state: State, move: Move) -> State:
    """Apply one move and return a new immutable state."""
    new_tableau = [list(col) for col in state.tableau]
    new_freecells = list(state.freecells)
    new_foundations = [list(f) for f in state.foundations]
    
    from_type, from_idx = move.from_pos
    to_type, to_idx = move.to_pos
    
    moving_cards = [move.card]
    
    if from_type == 'tableau':
        col = new_tableau[from_idx]
        try:
            card_idx = col.index(move.card)
            moving_cards = col[card_idx:]
            new_tableau[from_idx] = col[:card_idx]
        except ValueError:
            if col:
                moving_cards = [col.pop()]
    elif from_type == 'freecell':
        new_freecells[from_idx] = None
    
    if to_type == 'tableau':
        new_tableau[to_idx].extend(moving_cards)
    elif to_type == 'freecell':
        new_freecells[to_idx] = moving_cards[0]
    elif to_type == 'foundation':
        new_foundations[to_idx].append(moving_cards[0])
    
    return State(new_tableau, new_freecells, new_foundations)


def is_goal(state: State) -> bool:
    """Return True when all foundation piles contain 13 cards."""
    for foundation in state.foundations:
        if len(foundation) != 13:
            return False
    return True
