"""Core immutable data models for the FreeCell engine."""

from dataclasses import dataclass
from typing import List, Optional, Tuple


VALID_RANK = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
VALID_SUITS = ["hearts", "diamonds", "clubs", "spades"]
LOCATIONS = ["tableau", "freecell", "foundation"]


@dataclass(frozen=True, order=True)
class Card:
    """Playing card with validated suit/rank and cached numeric fields."""

    suit: str
    rank: str

    def __post_init__(self):
        if self.rank not in VALID_RANK:
            raise ValueError(f"Invalid rank: {self.rank}")
        if self.suit not in VALID_SUITS:
            raise ValueError(f"Invalid suit: {self.suit}")

        color = "red" if self.suit in ("hearts", "diamonds") else "black"
        rank_val = VALID_RANK.index(self.rank) + 1
        suit_idx = VALID_SUITS.index(self.suit)

        object.__setattr__(self, "color", color)
        object.__setattr__(self, "rank_val", rank_val)
        object.__setattr__(self, "suit_idx", suit_idx)
        object.__setattr__(self, "_id", suit_idx * 13 + rank_val)

    def to_int(self) -> int:
        return self._id


@dataclass(frozen=True)
class State:
    """Immutable game state snapshot used by search algorithms."""

    tableau: Tuple[Tuple[Card, ...], ...]
    freecells: Tuple[Optional[Card], ...]
    foundations: Tuple[Tuple[Card, ...], ...]

    def __init__(self, tableau: List[List[Card]], freecells: List[Optional[Card]], foundations: List[List[Card]]):
        object.__setattr__(self, "tableau", tuple(tuple(col) for col in tableau))
        object.__setattr__(self, "freecells", tuple(freecells))
        object.__setattr__(self, "foundations", tuple(tuple(stack) for stack in foundations))
        object.__setattr__(self, "_board_int", self._encode_board())

    def _encode_board(self) -> int:
        foundation_value = 0
        for stack in self.foundations:
            foundation_value = (foundation_value << 4) | len(stack)

        freecell_cards = sorted(card.to_int() for card in self.freecells if card is not None)
        freecell_value = 0
        for idx in range(4):
            value = freecell_cards[idx] if idx < len(freecell_cards) else 0
            freecell_value = (freecell_value << 6) | value

        column_values = []
        for column in self.tableau:
            encoded_column = 0
            for card in column:
                encoded_column = (encoded_column << 6) | card.to_int()
            column_values.append(encoded_column)
        column_values.sort()

        tableau_value = 0
        for encoded_column in column_values:
            tableau_value = (tableau_value << 120) | encoded_column

        return (tableau_value << 40) | (freecell_value << 16) | foundation_value

    def __eq__(self, other):
        if not isinstance(other, State):
            return False
        return self._board_int == other._board_int

    def __hash__(self):
        return hash(self._board_int)


@dataclass(frozen=True)
class Move:
    """Represents a legal move in the game state graph."""

    move_type: str
    card: Card
    from_pos: Tuple[str, int]
    to_pos: Tuple[str, int]