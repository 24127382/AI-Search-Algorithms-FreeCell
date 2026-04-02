from random import Random
from typing import Sequence

from backend.model.card import VALID_RANK, VALID_SUITS, Card

_MS_RAND_MULTIPLIER = 214013
_MS_RAND_INCREMENT = 2531011
_MS_RAND_MASK = 0x7FFFFFFF
_MS_SUIT_MAP = {"C": "clubs", "D": "diamonds", "H": "hearts", "S": "spades"}


def _microsoft_rand_stream(seed: int) -> tuple[int, ...]:
    """Generate the first 52 values of Microsoft CRT `rand()` sequence.

    Args:
            seed: Deal number used as random seed.

    Returns:
            tuple[int, ...]: Sequence of 52 pseudo-random integers.
    """
    state = seed & _MS_RAND_MASK
    values: list[int] = []
    for _ in range(52):
        state = (_MS_RAND_MULTIPLIER * state + _MS_RAND_INCREMENT) & _MS_RAND_MASK
        values.append((state >> 16) & 0x7FFF)
    return tuple(values)


def microsoft_shuffled_deck(deal_number: int) -> tuple[Card, ...]:
    """Build a deck shuffled with classic Microsoft FreeCell rules.

    Args:
            deal_number: Microsoft deal number.

    Returns:
            tuple[Card, ...]: Shuffled 52-card deck.

    """
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
    """Distribute a 52-card sequence into eight tableau columns.

    Args:
            cards: Ordered card sequence.

    Returns:
            tuple[tuple[Card, ...], ...]: Tableau columns in deal order.

    Raises:
            ValueError: If card count is not exactly 52.
    """
    if len(cards) != 52:
        raise ValueError(f"FreeCell requires 52 cards, got {len(cards)}")

    tableau: list[list[Card]] = [[] for _ in range(8)]
    for idx, card in enumerate(cards):
        tableau[idx % 8].append(card)
    return tuple(tuple(column) for column in tableau)


def deal() -> tuple[int, tuple[tuple[Card, ...], ...]]:
    """Pick a random deal number and return its tableau.

    Returns:
            tuple[int, tuple[tuple[Card, ...], ...]]: Chosen game number and tableau.
    """
    game_number = random_deal_number()
    tableau = _to_tableau(microsoft_shuffled_deck(game_number))
    return game_number, tableau


def random_deal_number() -> int:
    """Return one random deal number.

    Returns:
            int: Random 63-bit non-negative integer.
    """
    return Random().getrandbits(63)


def deal_random() -> tuple[tuple[Card, ...], ...]:
    """Deal a random FreeCell tableau without a deal number.

    Returns:
            tuple[tuple[Card, ...], ...]: Randomly shuffled tableau.
    """
    deck = [Card(suit=suit, rank=rank) for suit in VALID_SUITS for rank in VALID_RANK]
    Random().shuffle(deck)
    return _to_tableau(deck)


def deal_by_game_number(game_number: int) -> tuple[tuple[Card, ...], ...]:
    """Build tableau for a specific Microsoft deal number.

    Args:
            game_number: Microsoft deal number.

    Returns:
            tuple[tuple[Card, ...], ...]: Tableau for this deal.

    """
    tableau = _to_tableau(microsoft_shuffled_deck(game_number))
    return tableau
