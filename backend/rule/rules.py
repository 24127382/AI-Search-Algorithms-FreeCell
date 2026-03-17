from functools import lru_cache
from typing import Iterable, List, Sequence, Tuple

from backend.model.card import Card
from backend.model.move import Move, MoveType
from backend.model.state import State

_RED_OPP_FOUNDATION_IDX = (2, 3)
_BLACK_OPP_FOUNDATION_IDX = (0, 1)
_MAX_FREECELLS = 4
_MAX_TABLEAU_COLUMNS = 8
_SUPERMOVE_LIMITS = {
    (empty_freecells, empty_tableau): (empty_freecells + 1) * (2 ** empty_tableau)
    for empty_freecells in range(_MAX_FREECELLS + 1)
    for empty_tableau in range(_MAX_TABLEAU_COLUMNS + 1)
}
_SUPERMOVE_TO_EMPTY_LIMITS = {
    (empty_freecells, empty_tableau): (empty_freecells + 1) * (2 ** max(empty_tableau - 1, 0))
    for empty_freecells in range(_MAX_FREECELLS + 1)
    for empty_tableau in range(_MAX_TABLEAU_COLUMNS + 1)
}


def _card_rank(card_id: int) -> int:
    return ((card_id - 1) % 13) + 1


def _is_red(card_id: int) -> bool:
    return ((card_id - 1) // 13) < 2


def _build_tableau_pair_lookup() -> tuple[tuple[bool, ...], ...]:
    matrix = [[False] * 53 for _ in range(53)]
    for card_id in range(1, 53):
        rank = _card_rank(card_id)
        is_red = _is_red(card_id)
        for top_id in range(1, 53):
            top_rank = _card_rank(top_id)
            top_is_red = _is_red(top_id)
            matrix[card_id][top_id] = (rank == top_rank - 1) and (is_red != top_is_red)
    return tuple(tuple(row) for row in matrix)


_TABLEAU_PAIR_VALID = _build_tableau_pair_lookup()

def can_move_to_foundation(card: Card, foundation: Tuple[Card, ...], f_idx: int) -> bool:
    """Check if card can move to foundation (same suit, rank+1, matches assigned foundation index)."""
    if card.suit_idx != f_idx:
        return False

    return card.rank_val == len(foundation) + 1

def is_safe_to_foundation(state: State, card: Card) -> bool:
    """Check if moving a card to the foundation is universally safe."""
    rank_val = card.rank_val
    if rank_val <= 2:
        return True # Aces and Twos are always safe

    opp_foundation_idx = _RED_OPP_FOUNDATION_IDX if card.color == 'red' else _BLACK_OPP_FOUNDATION_IDX
    for suit_idx in opp_foundation_idx:
        if len(state.foundations[suit_idx]) < rank_val - 1:
            return False
    return True

def can_move_to_tableau(card: Card, tableau_col: Tuple[Card, ...]) -> bool:
    """Check if card can move to tableau column (rank-1, opposite color)."""
    if not tableau_col:
        return True

    top_card = tableau_col[-1]
    return _TABLEAU_PAIR_VALID[card.to_int()][top_card.to_int()]


@lru_cache(maxsize=50000)
def _get_movable_sequences_cached(column: Tuple[Card, ...]) -> Tuple[Tuple[Card, ...], ...]:
    if not column:
        return tuple()

    sequences = [tuple([column[-1]])]
    start_idx = len(column) - 1

    for idx in range(len(column) - 2, -1, -1):
        below_card = column[idx]
        above_card = column[idx + 1]

        if not _is_valid_sequence_pair(below_card, above_card):
            break

        start_idx = idx
        sequences.append(tuple(column[start_idx:]))

    return tuple(sequences)


def get_movable_sequences(column: Tuple[Card, ...]) -> Tuple[Tuple[Card, ...], ...]:
    """Extract all valid movable sequences from top of column."""
    return _get_movable_sequences_cached(column)


def _is_valid_sequence_pair(card1: Card, card2: Card) -> bool:
    """Check if card1 (below) and card2 (above) form valid sequence pair."""
    return _TABLEAU_PAIR_VALID[card2.to_int()][card1.to_int()]


def find_valid_destinations(
    state: State,
    sequence: Sequence[Card],
    from_pos: Tuple[str, int],
    max_seq_len: int,
) -> List[Move]:
    """Find all valid destinations for a movable sequence."""
    if len(sequence) > max_seq_len:
        return []

    valid_destinations = []
    base_card = sequence[0]
    
    if len(sequence) == 1:
        for f_idx, foundation in enumerate(state.foundations):
            if can_move_to_foundation(base_card, foundation, f_idx):
                move = Move(
                    MoveType.TABLEAU_TO_FOUNDATION if from_pos[0] == 'tableau' else MoveType.FREECELL_TO_FOUNDATION,
                    base_card,
                    from_pos,
                    ('foundation', f_idx),
                    sequence=tuple(sequence),
                )
                valid_destinations.append(move)
    
    for t_idx, tableau_col in enumerate(state.tableau):
        if from_pos[0] == 'tableau' and t_idx == from_pos[1]:
            continue

        if can_move_to_tableau(base_card, tableau_col):
            is_valid_len = True
            if not tableau_col:
                max_to_empty = get_max_sequence_to_empty_tableau(state)
                if len(sequence) > max_to_empty:
                    is_valid_len = False
            
            if is_valid_len:
                move = Move(
                    MoveType.TABLEAU_TO_TABLEAU if from_pos[0] == 'tableau' else MoveType.FREECELL_TO_TABLEAU,
                    base_card,
                    from_pos,
                    ('tableau', t_idx),
                    sequence=tuple(sequence),
                )
                valid_destinations.append(move)
    
    if len(sequence) == 1 and from_pos[0] == 'tableau':
        for c_idx, cell in enumerate(state.freecells):
            if cell is None:
                move = Move(
                    MoveType.TABLEAU_TO_FREECELL,
                    base_card,
                    from_pos,
                    ('freecell', c_idx),
                    sequence=tuple(sequence),
                )
                valid_destinations.append(move)
    
    return valid_destinations


def get_max_sequence_length(state: State) -> int:
    """Calculate max sequence length using supermove rule: K = (F + 1) * 2^E."""
    empty_freecells = sum(1 for cell in state.freecells if cell is None)
    empty_tableau_cols = sum(1 for col in state.tableau if len(col) == 0)

    return _SUPERMOVE_LIMITS[(empty_freecells, empty_tableau_cols)]


def get_max_sequence_to_empty_tableau(state: State) -> int:
    """Max sequence length when destination tableau is empty: (F + 1) * 2^(E - 1)."""
    empty_freecells = sum(1 for cell in state.freecells if cell is None)
    empty_tableau_cols = sum(1 for col in state.tableau if len(col) == 0)
    return _SUPERMOVE_TO_EMPTY_LIMITS[(empty_freecells, empty_tableau_cols)]
