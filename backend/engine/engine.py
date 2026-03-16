"""
engine.py 

Game engine for FreeCell card game.
Implements core game logic: move validation and state transitions.

Core Functions:
- get_valid_moves: Returns all legal moves from current game state
- apply_move: Applies a move to the state and returns new state
- is_goal: Checks if game is won (all cards in foundations)
"""

from typing import List
from backend.model.models import State, Move
from backend.rule.rules import get_max_sequence_length, get_movable_sequences, find_valid_destinations, is_safe_to_foundation

def get_valid_moves(state: State, prune_safe: bool = True) -> List[Move]:
    '''
    Returns all valid moves from the current state.
    Purpose: Generate legal moves for search algorithm to explore.
    Workflow: Iterate over tableau and freecells, find movable sequences, and check valid destinations.
    Respects supermove rule: K = (F + 1) * 2^E (max sequence length limitation).
    '''
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

    # Auto-move pruning: if any move to foundation is "safe", it's a dominant move.
    # Return JUST that single safe move so the solver won't branch on anything else!
    if prune_safe:
        for move in moves:
            if move.to_pos[0] == 'foundation' and is_safe_to_foundation(state, move.card):
                return [move]

    return moves

def apply_move(state: State, move: Move) -> State:
    """Apply move to state and return new state (immutable)."""
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
    """Check if game is won (all foundations have 13 cards)."""
    for foundation in state.foundations:
        if len(foundation) != 13:
            return False
    return True
