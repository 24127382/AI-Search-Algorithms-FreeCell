from random import Random
from typing import Sequence

from backend.model.card import Card, VALID_RANK, VALID_SUITS


_MS_RAND_MULTIPLIER = 214013
_MS_RAND_INCREMENT = 2531011
_MS_RAND_MASK = 0x7FFFFFFF
_MS_SUIT_MAP = {"C": "clubs", "D": "diamonds", "H": "hearts", "S": "spades"}
_DIFFICULTY_LEVELS = ("easy", "medium", "hard", "expert")
_SOLVED_GAME_NUMBERS_BY_DIFFICULTY: dict[str, tuple[int, ...]] = {
	"easy": (1, 2, 3, 4, 6, 7, 8, 10, 12, 14, 17, 20, 24, 30, 38, 45),
	"medium": (52, 63, 77, 81, 96, 104, 118, 126, 139, 157, 173, 188, 204, 229, 251, 279),
	"hard": (301, 337, 389, 417, 468, 512, 579, 624, 711, 758, 824, 907, 961, 1033, 1177, 1291),
	"expert": (1369, 1458, 1597, 1724, 1888, 2019, 2197, 2333, 2548, 2791, 3017, 3371, 3908, 4217, 4899, 5631),
}


def _microsoft_rand_stream(seed: int) -> tuple[int, ...]:
	"""Return 52 outputs from the Microsoft C runtime rand() sequence."""
	state = seed & _MS_RAND_MASK
	values: list[int] = []
	for _ in range(52):
		state = (_MS_RAND_MULTIPLIER * state + _MS_RAND_INCREMENT) & _MS_RAND_MASK
		values.append((state >> 16) & 0x7FFF)
	return tuple(values)

def microsoft_shuffled_deck(deal_number: int) -> tuple[Card, ...]:
	"""Shuffle using the classic Microsoft FreeCell deal algorithm."""
	if deal_number < 0:
		raise ValueError("deal_number must be non-negative")

	deck = [
		Card(
			suit=_MS_SUIT_MAP["CDHS"[value % 4]],
			rank=VALID_RANK[value // 4],
		)
		for value in range(51, -1, -1)
	]
	for i, rand_value in zip(range(len(deck)), _microsoft_rand_stream(deal_number)):
		swap_idx = (len(deck) - 1) - (rand_value % (len(deck) - i))
		deck[i], deck[swap_idx] = deck[swap_idx], deck[i]
	return tuple(deck)

def _to_tableau(cards: Sequence[Card]) -> tuple[tuple[Card, ...], ...]:
	"""Deal a 52-card sequence into 8 tableau columns."""
	if len(cards) != 52:
		raise ValueError(f"FreeCell requires 52 cards, got {len(cards)}")

	tableau: list[list[Card]] = [[] for _ in range(8)]
	for idx, card in enumerate(cards):
		tableau[idx % 8].append(card)
	return tuple(tuple(column) for column in tableau)

def _normalize_difficulty(difficulty: str) -> str:
	normalized = (difficulty or "medium").strip().lower()
	if normalized not in _DIFFICULTY_LEVELS:
		valid = ", ".join(_DIFFICULTY_LEVELS)
		raise ValueError(f"Invalid difficulty '{difficulty}'. Expected one of: {valid}")
	return normalized


def deal(difficulty: str = "medium") -> tuple[int, tuple[tuple[Card, ...], ...]]:
	"""Deal one solved game by difficulty and return (game_number, tableau)."""
	normalized = _normalize_difficulty(difficulty)
	game_number = Random().choice(_SOLVED_GAME_NUMBERS_BY_DIFFICULTY[normalized])
	tableau = _to_tableau(microsoft_shuffled_deck(game_number))
	return game_number, tableau


def deal_random() -> tuple[tuple[Card, ...], ...]:
    """Deal random it doesn't have a game number."""
    deck = [Card(suit=suit, rank=rank) for suit in VALID_SUITS for rank in VALID_RANK]
    Random().shuffle(deck)
    return _to_tableau(deck)

def deal_by_game_number(game_number: int) -> tuple[tuple[Card, ...], ...]:
    """Deal a specific game number using the Microsoft shuffle algorithm."""
    if game_number < 0:
        raise ValueError("game_number must be non-negative")
    tableau = _to_tableau(microsoft_shuffled_deck(game_number))
    return tableau