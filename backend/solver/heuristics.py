"""Heuristic helpers for informed search algorithms."""


def zero_heuristic(_state) -> int:
	"""Return zero heuristic value.

	Args:
		_state: Unused state argument kept for heuristic signature compatibility.

	Returns:
		int: Always `0`.
	"""
	return 0


def cards_remaining_heuristic(state) -> int:
	"""Estimate remaining distance by counting non-foundation cards.

	Args:
		state: Current board state.

	Returns:
		int: Number of cards not yet placed in foundations.
	"""
	foundation_cards = sum(len(stack) for stack in state.foundations)
	return 52 - foundation_cards