"""Card asset constants and lookup helpers for frontend rendering."""

import os

from backend.model.card import Card


SUIT_SYMBOL = {
	"hearts": "♥",
	"diamonds": "♦",
	"clubs": "♣",
	"spades": "♠",
}


def card_asset_path(card: Card) -> str:
	"""Return filesystem path of PNG matching a given card.

	Args:
		card: Card model instance.

	Returns:
		str: Relative path to card image file.
	"""
	rank = card.rank
	if rank.isdigit() and len(rank) == 1:
		rank = f"0{rank}"
	filename = f"card_{card.suit}_{rank}.png"
	return os.path.join("asset", "card", filename)
