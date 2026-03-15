import os

from backend.model.models import Card


SUIT_SYMBOL = {
	"hearts": "♥",
	"diamonds": "♦",
	"clubs": "♣",
	"spades": "♠",
}


def card_asset_path(card: Card) -> str:
	rank = card.rank
	if rank.isdigit() and len(rank) == 1:
		rank = f"0{rank}"
	filename = f"card_{card.suit}_{rank}.png"
	return os.path.join("asset", "card", filename)
