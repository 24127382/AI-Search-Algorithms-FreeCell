"""
engine.py 

Game engine for FreeCell card game.
Implements core game logic: move validation and state transitions.

Core Functions:
- get_valid_moves: Returns all legal moves from current game state
- apply_move: Applies a move to the state and returns new state
- is_goal: Checks if game is won (all cards in foundations)
"""

from typing import List, Tuple
from backend.models import State, Move, Card, VALID_RANK


def can_move_to_foundation(card: Card, foundation: Tuple[Card, ...]) -> bool:
    """Check if card can move to foundation (same suit, rank+1)."""
    if not foundation:
        return card.rank == 'A'
    
    top_card = foundation[-1]
    
    if card.suit != top_card.suit:
        return False
    
    top_idx = VALID_RANK.index(top_card.rank)
    card_idx = VALID_RANK.index(card.rank)
    
    return card_idx == top_idx + 1


def can_move_to_tableau(card: Card, tableau_col: Tuple[Card, ...]) -> bool:
    """Check if card can move to tableau column (rank-1, opposite color)."""
    if not tableau_col:
        return True
    
    top_card = tableau_col[-1]
    
    top_idx = VALID_RANK.index(top_card.rank)
    card_idx = VALID_RANK.index(card.rank)
    
    if card_idx != top_idx - 1:
        return False
    
    return card.color != top_card.color


def get_movable_sequences(column: Tuple[Card, ...]) -> List[List[Card]]:
    """Extract all valid movable sequences from top of column."""
    if not column:
        return []
    
    sequences = []
    current_sequence = [column[-1]]
    
    for i in range(len(column) - 2, -1, -1):
        top_card = column[i + 1]
        under_card = column[i]
        
        if _is_valid_sequence_pair(under_card, top_card):
            current_sequence.append(under_card)
            sequences.append(list(reversed(current_sequence)))
        else:
            break
    
    return sequences


def _is_valid_sequence_pair(card1: Card, card2: Card) -> bool:
    """Check if card1 (below) and card2 (above) form valid sequence pair."""
    try:
        rank1_idx = VALID_RANK.index(card1.rank)
        rank2_idx = VALID_RANK.index(card2.rank)
    except ValueError:
        return False
    
    # check if the ranks are in descending order 
    rank_matches = (rank1_idx == rank2_idx + 1)
    # check if the colors are alternating
    color_matches = (card1.color != card2.color)
    
    return rank_matches and color_matches


def find_valid_destinations(state: State, sequence: List[Card], from_pos: Tuple[str, int]) -> List[Move]:
    """Find all valid destinations for a movable sequence."""
    valid_destinations = []
    bottom_card = sequence[-1]
    
    if len(sequence) == 1:
        for f_idx, foundation in enumerate(state.foundations):
            if can_move_to_foundation(bottom_card, foundation):
                move = Move('to_foundation', bottom_card, from_pos, ('foundation', f_idx))
                valid_destinations.append(move)
    
    for t_idx, tableau_col in enumerate(state.tableau):
        if can_move_to_tableau(bottom_card, tableau_col):
            move = Move('to_tableau', bottom_card, from_pos, ('tableau', t_idx))
            valid_destinations.append(move)
    
    if len(sequence) == 1:
        for c_idx, cell in enumerate(state.freecells):
            if cell is None:
                move = Move('to_freecell', bottom_card, from_pos, ('freecell', c_idx))
                valid_destinations.append(move)
    
    return valid_destinations


def get_max_sequence_length(state: State) -> int:
    """Calculate max sequence length using supermove rule: K = (F + 1) × 2^E."""
    empty_freecells = sum(1 for cell in state.freecells if cell is None)
    empty_tableau_cols = sum(1 for col in state.tableau if len(col) == 0)
    
    K = (empty_freecells + 1) * (2 ** empty_tableau_cols)
    return K


def get_valid_moves(state: State) -> List[Move]:
    '''
    Returns all valid moves from the current state.
    Purpose: Generate legal moves for search algorithm to explore.
    Workflow: Iterate over tableau and freecells, find movable sequences, and check valid destinations.
    Respects supermove rule: K = (F + 1) × 2^E (max sequence length limitation).
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
    
    return moves


def apply_move(state: State, move: Move) -> State:
    """Apply move to state and return new state (immutable)."""
    new_tableau = [list(col) for col in state.tableau]
    new_freecells = list(state.freecells)
    new_foundations = [list(f) for f in state.foundations]
    
    from_type, from_idx = move.from_pos
    to_type, to_idx = move.to_pos
    
    if from_type == 'tableau':
        new_tableau[from_idx].pop()
    elif from_type == 'freecell':
        new_freecells[from_idx] = None
    
    if to_type == 'tableau':
        new_tableau[to_idx].append(move.card)
    elif to_type == 'freecell':
        new_freecells[to_idx] = move.card
    elif to_type == 'foundation':
        new_foundations[to_idx].append(move.card)
    
    return State(new_tableau, new_freecells, new_foundations)


def is_goal(state: State) -> bool:
    """Check if game is won (all foundations have 13 cards)."""
    for foundation in state.foundations:
        if len(foundation) != 13:
            return False
    return True