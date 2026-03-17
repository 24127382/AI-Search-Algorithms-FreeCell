"""Card model and card-related constants."""

from dataclasses import dataclass, field


VALID_RANK = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
VALID_SUITS = ["hearts", "diamonds", "clubs", "spades"]
LOCATIONS = ["tableau", "freecell", "foundation"]


@dataclass(frozen=True, order=True)
class Card:
    """Playing card with validated suit/rank and cached numeric fields."""

    suit: str
    rank: str

    color: str = field(init=False, repr=False, compare=False)
    rank_val: int = field(init=False, repr=False, compare=False)
    suit_idx: int = field(init=False, repr=False, compare=False)
    _id: int = field(init=False, repr=False, compare=False)

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
