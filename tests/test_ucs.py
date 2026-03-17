import pytest

from backend.engine.engine import apply_move
from backend.model.card import Card, VALID_RANK, VALID_SUITS
from backend.model.state import State
from backend.solver.ucs import UCSAlgorithm


def _build_near_goal_state() -> State:
	foundations = []
	for suit in VALID_SUITS:
		foundation_stack = [Card(suit=suit, rank=rank) for rank in VALID_RANK[:-1]]
		foundations.append(foundation_stack)

	kings = [Card(suit=suit, rank="K") for suit in VALID_SUITS]
	tableau = [[king] for king in kings] + [[] for _ in range(4)]

	return State.from_lists(
		tableau=tableau,
		freecells=[None, None, None, None],
		foundations=foundations,
	)


def _replay_path(state: State, path):
	current = state
	for move in path:
		current = apply_move(current, move)
	return current


@pytest.mark.parametrize("mode", ["fast", "exact"])
def test_ucs_solves_near_goal(mode):
	start_state = _build_near_goal_state()
	solver = UCSAlgorithm(start_state, mode=mode)

	path = solver.search()

	assert path is not None
	assert len(path) == 4

	end_state = _replay_path(start_state, path)
	assert end_state.is_goal


def test_ucs_returns_empty_path_if_already_goal():
	foundations = []
	for suit in VALID_SUITS:
		foundations.append([Card(suit=suit, rank=rank) for rank in VALID_RANK])

	state = State.from_lists(
		tableau=[[] for _ in range(8)],
		freecells=[None, None, None, None],
		foundations=foundations,
	)

	path = UCSAlgorithm(state, mode="fast").search()

	assert path == []


def test_ucs_rejects_invalid_mode():
	state = _build_near_goal_state()

	with pytest.raises(ValueError, match="Unsupported UCS mode"):
		UCSAlgorithm(state, mode="invalid")
