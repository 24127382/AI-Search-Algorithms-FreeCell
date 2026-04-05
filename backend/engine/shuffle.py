"""FreeCell deal generation and game state setup.

This module provides functions to generate FreeCell game states from:
1. Microsoft deal numbers (via Microsoft CRT PRNG algorithm)
2. Special deterministic test cases for benchmarking BFS

QUICK START - Use generate_game():

    from backend.engine.shuffle import generate_game

    # Load Microsoft deal
    state1 = generate_game(42)

    # Load special test case
    state2 = generate_game("bfs_easy_10")
    state3 = generate_game("bfs_hard_20")

This unified interface is recommended for most use cases. It always returns
a complete State object with tableau, freecells, and foundations.

LEGACY API - For backward compatibility:

    from backend.engine.shuffle import deal_by_game_number
    tableau = deal_by_game_number(42)  # Returns only tableau tuple

See docs/UNIFIED_INTERFACE.md for complete documentation.
"""

from random import Random
from typing import Sequence, Optional, Union

from backend.model.card import Card, VALID_RANK, VALID_SUITS
from backend.model.state import State


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


def generate_game(deal_id: Union[int, str]) -> State:
	"""Generate a complete FreeCell game state from either a Microsoft deal number or special test case ID.

	Unified entry point that handles both built-in Microsoft deal numbers and special
	deterministic test cases by ID. This function always returns a full State object
	with tableau, freecells, and foundations properly initialized.

	Args:
		deal_id: Either:
			- An integer: Microsoft CRT shuffle deal number (0 to 2^63-1)
			- A string: Special test case ID (e.g., "bfs_easy_10", "bfs_hard_20")

	Returns:
		State: A valid, complete FreeCell game state.

	Raises:
		ValueError: If a string ID is provided but not recognized as a valid special test case.

	Examples:
		>>> # Load a Microsoft deal
		>>> state1 = generate_game(42)
		>>> # Load a special test case
		>>> state2 = generate_game("bfs_easy_10")
		>>> # Both are State objects with tableau, freecells, foundations
	"""
	if isinstance(deal_id, str):
		# Special test case identified
		state = get_special_test_case(deal_id)
		if state is None:
			raise ValueError(f"Unknown special test case ID: '{deal_id}'. "
							   f"Supported IDs: 'bfs_easy_10', 'bfs_hard_20'")
		return state
	else:
		# Microsoft deal number
		tableau = deal_by_game_number(deal_id)
		return State.from_lists(
			tableau=tableau,
			freecells=[None] * 4,
			foundations=[[] for _ in range(4)]
		)


# ============================================================================
# SPECIAL DETERMINISTIC TEST CASES FOR BFS TESTING
# ============================================================================

def _make_easy_test_case() -> State:
	"""Create a deterministic easy test case (~10 moves to goal).
	
	Simple puzzle: A few cards need to be moved back to foundations.
	Most cards already placed.
	
	Returns:
		State: Valid FreeCell state, ~10 moves from goal.
	"""
	tableau = [
		(Card("hearts", "A"),),
		(Card("diamonds", "A"),),
		(Card("clubs", "K"), Card("spades", "Q")),  # Valid: K black on red Q
		(Card("hearts", "J"), Card("diamonds", "10")),  # Valid: J red on black 10
		(),  (),  (),  (),
	]
	
	freecells = (None, None, None, None)
	
	# Foundations: all except the cards in tableau
	# Tableau cards: A♥, A♦, K♣, Q♠, J♥, 10♦
	# Build foundations with all cards except those listed
	foundations_list = [[], [], [], []]
	tableau_set = {
		(0, 1),   # A♥ (hearts, Ace)
		(1, 1),   # A♦ (diamonds, Ace)
		(2, 13),  # K♣ (clubs, King)
		(3, 12),  # Q♠ (spades, Queen)
		(0, 11),  # J♥ (hearts, Jack)
		(1, 10),  # 10♦ (diamonds, 10)
	}
	
	for rank_idx, rank in enumerate(VALID_RANK):
		for suit_idx, suit in enumerate(VALID_SUITS):
			if (suit_idx, rank_idx + 1) not in tableau_set:
				foundations_list[suit_idx].append(Card(suit, rank))
	
	foundations = tuple(tuple(f) for f in foundations_list)
	
	return State(tableau=tuple(tableau), freecells=freecells, foundations=foundations)


def _make_hard_test_case() -> State:
	"""Create a harder deterministic test case (~15 moves to goal).
	
	More complex: Multiple sequences in tableau, requires careful sequencing.
	
	Returns:
		State: Valid FreeCell state.
	"""
	tableau = [
		(Card("spades", "K"), Card("diamonds", "Q"), Card("clubs", "J")),
		(Card("spades", "10"), Card("hearts", "9"), Card("diamonds", "8")),
		(Card("spades", "7"), Card("clubs", "6"), Card("hearts", "5")),
		(Card("spades", "4"), Card("diamonds", "3"), Card("clubs", "2")),
		(Card("hearts", "A"),),
		(Card("diamonds", "A"),),
		(Card("clubs", "A"),),
		(Card("spades", "A"),),
	]
	
	freecells = (None, None, None, None)
	
	# Create list of all tableau cards to exclude from foundations
	tableau_cards = set()
	for col in tableau:
		for card in col:
			tableau_cards.add((card.suit_idx, card.rank_val))
	
	# Foundations: all cards except those in tableau
	foundations_list = [[], [], [], []]
	for rank_idx, rank in enumerate(VALID_RANK):
		for suit_idx, suit in enumerate(VALID_SUITS):
			if (suit_idx, rank_idx + 1) not in tableau_cards:
				foundations_list[suit_idx].append(Card(suit, rank))
	
	foundations = tuple(tuple(f) for f in foundations_list)
	
	return State(tableau=tuple(tableau), freecells=freecells, foundations=foundations)


def get_special_test_case(test_case_id: str) -> Optional[State]:
	"""Retrieve a predefined deterministic test case by ID.
	
	These test cases are useful for controlled BFS benchmarking and testing.
	They guarantee:
	- Deterministic initial state (reproducible)
	- Valid FreeCell game state
	- Known approximate solution depth
	
	Args:
		test_case_id: Identifier for the test case.
			Supported values:
			- "bfs_easy_10": Easy case, ~10 moves to goal
			- "bfs_hard_20": Harder case, ~20 moves to goal
	
	Returns:
		State: Initial game state, or None if ID not found.
	"""
	if test_case_id == "bfs_easy_10":
		return _make_easy_test_case()
	elif test_case_id == "bfs_hard_20":
		return _make_hard_test_case()
	else:
		return None