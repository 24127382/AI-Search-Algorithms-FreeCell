from typing import List, Tuple

from backend.model.models import Card, Move, State, VALID_RANK, VALID_SUITS


def _rank_index(rank: str) -> int:
    return VALID_RANK.index(rank)

def can_move_to_foundation(card: Card, foundation: Tuple[Card, ...], f_idx: int) -> bool:
    """Check if card can move to foundation (same suit, rank+1, matches assigned foundation index)."""
    target_suit = VALID_SUITS[f_idx]
    if card.suit != target_suit:
        return False

    if not foundation:
        return card.rank == 'A'
    
    top_card = foundation[-1]
    
    top_idx = _rank_index(top_card.rank)
    card_idx = _rank_index(card.rank)
    
    return card_idx == top_idx + 1

def is_safe_to_foundation(state: State, card: Card) -> bool:
    """Check if moving a card to the foundation is universally safe."""
    rank_val = _rank_index(card.rank) + 1
    if rank_val <= 2:
        return True # Aces and Twos are always safe
        
    opp_suits = ['clubs', 'spades'] if card.color == 'red' else ['hearts', 'diamonds']
    for suit in opp_suits:
        suit_idx = VALID_SUITS.index(suit)
        if len(state.foundations[suit_idx]) < rank_val - 1:
            return False
    return True

def can_move_to_tableau(card: Card, tableau_col: Tuple[Card, ...]) -> bool:
    """Check if card can move to tableau column (rank-1, opposite color)."""
    if not tableau_col:
        return True
    
    top_card = tableau_col[-1]
    
    top_idx = _rank_index(top_card.rank)
    card_idx = _rank_index(card.rank)
    
    if card_idx != top_idx - 1:
        return False
    
    return card.color != top_card.color


def get_movable_sequences(column: Tuple[Card, ...]) -> List[List[Card]]:
    """Extract all valid movable sequences from top of column."""
    if not column:
        return []
    
    sequences = []
    current_sequence = [column[-1]]
    sequences.append(list(current_sequence))
    
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
        rank1_idx = _rank_index(card1.rank)
        rank2_idx = _rank_index(card2.rank)
    except ValueError:
        return False
    
    rank_matches = (rank1_idx == rank2_idx + 1)
    color_matches = (card1.color != card2.color)
    
    return rank_matches and color_matches


def find_valid_destinations(state: State, sequence: List[Card], from_pos: Tuple[str, int]) -> List[Move]:
    """Find all valid destinations for a movable sequence."""
    valid_destinations = []
    base_card = sequence[0]
    
    if len(sequence) == 1:
        for f_idx, foundation in enumerate(state.foundations):
            if can_move_to_foundation(base_card, foundation, f_idx):
                move = Move('to_foundation', base_card, from_pos, ('foundation', f_idx))
                valid_destinations.append(move)
    
    for t_idx, tableau_col in enumerate(state.tableau):
        if can_move_to_tableau(base_card, tableau_col):
            is_valid_len = True
            if not tableau_col:
                max_k = get_max_sequence_length(state)
                if len(sequence) > (max_k // 2):
                    is_valid_len = False
            
            if is_valid_len:
                move = Move('to_tableau', base_card, from_pos, ('tableau', t_idx))
                valid_destinations.append(move)
    
    if len(sequence) == 1:
        for c_idx, cell in enumerate(state.freecells):
            if cell is None:
                move = Move('to_freecell', base_card, from_pos, ('freecell', c_idx))
                valid_destinations.append(move)
    
    return valid_destinations


def get_max_sequence_length(state: State) -> int:
    """Calculate max sequence length using supermove rule: K = (F + 1) * 2^E."""
    empty_freecells = sum(1 for cell in state.freecells if cell is None)
    empty_tableau_cols = sum(1 for col in state.tableau if len(col) == 0)
    
    return (empty_freecells + 1) * (2 ** empty_tableau_cols)
