"""Heuristic helpers for informed search algorithms."""


def zero_heuristic(_state) -> int:
	"""Admissible baseline heuristic equivalent to UCS behavior."""
	return 0


def cards_remaining_heuristic(state) -> int:
	"""Simple admissible estimate: number of cards not yet in foundations."""
	foundation_cards = sum(len(stack) for stack in state.foundations)
	return 52 - foundation_cards