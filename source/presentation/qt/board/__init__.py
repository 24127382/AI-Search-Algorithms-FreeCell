"""Board presentation package exports."""

from source.presentation.qt.board.constants import (
	SLOT_FOUNDATION,
	SLOT_FREECELL,
	SLOT_TABLEAU,
)
from source.presentation.qt.board.widget import BoardWidget

__all__ = [
	"BoardWidget",
	"SLOT_TABLEAU",
	"SLOT_FREECELL",
	"SLOT_FOUNDATION",
]
