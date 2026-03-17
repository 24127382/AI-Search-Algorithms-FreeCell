"""Move model and move type enum."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from backend.model.card import Card


class MoveType(str, Enum):
    TABLEAU_TO_TABLEAU = "tableau_to_tableau"
    TABLEAU_TO_FREECELL = "tableau_to_freecell"
    TABLEAU_TO_FOUNDATION = "tableau_to_foundation"
    FREECELL_TO_TABLEAU = "freecell_to_tableau"
    FREECELL_TO_FOUNDATION = "freecell_to_foundation"


@dataclass(frozen=True)
class Move:
    """Represents a legal move in the game state graph."""

    move_type: MoveType
    card: Card
    from_pos: Tuple[str, int]
    to_pos: Tuple[str, int]
    sequence: Optional[Tuple[Card, ...]] = None
