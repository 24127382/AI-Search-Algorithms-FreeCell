"""Move model and move type enum."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from backend.model.card import Card


class MoveType(str, Enum):
    TABLEAU_TO_TABLEAU = "tableau_to_tableau"
    TABLEAU_TO_FREECELL = "tableau_to_freecell"
    TABLEAU_TO_FOUNDATION = "tableau_to_foundation"
    FREECELL_TO_FREECELL = "freecell_to_freecell"
    FREECELL_TO_TABLEAU = "freecell_to_tableau"
    FREECELL_TO_FOUNDATION = "freecell_to_foundation"


@dataclass(frozen=True)
class Move:
    """Represent one legal move in the game state graph.

    Attributes:
        move_type: Move category enum value.
        card: Base card associated with the move.
        from_pos: Source tuple `(slot_type, index)`.
        to_pos: Destination tuple `(slot_type, index)`.
        sequence: Optional moved sequence for tableau multi-card moves.
    """

    move_type: MoveType
    card: Card
    from_pos: Tuple[str, int]
    to_pos: Tuple[str, int]
    sequence: Optional[Tuple[Card, ...]] = None
