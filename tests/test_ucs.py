from backend.engine.engine import apply_move
from backend.model.card import Card, VALID_RANK, VALID_SUITS
from backend.model.move import Move, MoveType
from backend.model.state import State
from backend.solver.ucs import UCSAlgorithm
from backend.solver.ucs.ucs_utils import (
	is_breaking_stack,
	is_creating_empty_column,
	is_meaningless_empty_column_fill,
	ucs_move_cost,
)


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


def test_ucs_solves_near_goal():
	start_state = _build_near_goal_state()
	solver = UCSAlgorithm(start_state)

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

	path = UCSAlgorithm(state).search()

	assert path == []


def test_ucs_format_last_run_stats_before_search():
	solver = UCSAlgorithm(_build_near_goal_state())
	report = solver.format_last_run_stats()

	assert report == "No UCS stats available. Run search() first."


def test_ucs_format_last_run_stats_after_search_contains_core_metrics():
	solver = UCSAlgorithm(_build_near_goal_state())
	solver.search()
	report = solver.format_last_run_stats()

	assert "UCS Run Stats" in report
	assert "solution_found:" in report
	assert "elapsed_ms:" in report
	assert "expanded_nodes:" in report
	assert "effective_branching_factor:" in report


def test_ucs_cost_foundation_is_cheapest_progress_move():
	state = State.from_lists(
		tableau=[[Card("hearts", "A")]] + [[] for _ in range(7)],
		freecells=[None, None, None, None],
		foundations=[[], [], [], []],
	)

	move_to_foundation = Move(
		MoveType.TABLEAU_TO_FOUNDATION,
		Card("hearts", "A"),
		("tableau", 0),
		("foundation", 0),
		sequence=(Card("hearts", "A"),),
	)
	move_to_freecell = Move(
		MoveType.TABLEAU_TO_FREECELL,
		Card("hearts", "A"),
		("tableau", 0),
		("freecell", 0),
		sequence=(Card("hearts", "A"),),
	)

	assert ucs_move_cost(move_to_foundation, prev_state=state) < ucs_move_cost(move_to_freecell, prev_state=state)


def test_ucs_cost_penalizes_breaking_stack_and_rewards_empty_creation():
	breaking_state = State.from_lists(
		tableau=[[Card("spades", "9"), Card("hearts", "8")], []] + [[] for _ in range(6)],
		freecells=[None, None, None, None],
		foundations=[[], [], [], []],
	)
	breaking_move = Move(
		MoveType.TABLEAU_TO_FREECELL,
		Card("hearts", "8"),
		("tableau", 0),
		("freecell", 0),
		sequence=(Card("hearts", "8"),),
	)

	empty_creation_state = State.from_lists(
		tableau=[[Card("spades", "K")], [], []] + [[] for _ in range(5)],
		freecells=[None, None, None, None],
		foundations=[[], [], [], []],
	)
	empty_creation_move = Move(
		MoveType.TABLEAU_TO_TABLEAU,
		Card("spades", "K"),
		("tableau", 0),
		("tableau", 1),
		sequence=(Card("spades", "K"),),
	)

	assert is_breaking_stack(breaking_move, breaking_state)
	assert is_creating_empty_column(empty_creation_move, empty_creation_state)
	assert ucs_move_cost(breaking_move, prev_state=breaking_state) > ucs_move_cost(empty_creation_move, prev_state=empty_creation_state)


def test_ucs_cost_penalizes_meaningless_empty_column_fill():
	state = State.from_lists(
		tableau=[[Card("spades", "9"), Card("hearts", "7")], [], [Card("spades", "8")]] + [[] for _ in range(5)],
		freecells=[None, None, None, None],
		foundations=[[], [], [], []],
	)

	meaningless_fill_move = Move(
		MoveType.TABLEAU_TO_TABLEAU,
		Card("hearts", "7"),
		("tableau", 0),
		("tableau", 1),
		sequence=(Card("hearts", "7"),),
	)
	good_build_move = Move(
		MoveType.TABLEAU_TO_TABLEAU,
		Card("hearts", "7"),
		("tableau", 0),
		("tableau", 2),
		sequence=(Card("hearts", "7"),),
	)

	assert ucs_move_cost(meaningless_fill_move, prev_state=state) > ucs_move_cost(good_build_move, prev_state=state)


def test_ucs_meaningless_empty_fill_detects_short_sequences_not_only_singletons():
	state = State.from_lists(
		tableau=[
			[
				Card("spades", "K"),
				Card("hearts", "Q"),
				Card("clubs", "J"),
				Card("diamonds", "10"),
				Card("spades", "9"),
			],
			[],
		] + [[] for _ in range(6)],
		freecells=[None, None, None, None],
		foundations=[[], [], [], []],
	)

	move = Move(
		MoveType.TABLEAU_TO_TABLEAU,
		Card("diamonds", "10"),
		("tableau", 0),
		("tableau", 1),
		sequence=(Card("diamonds", "10"), Card("spades", "9")),
	)

	assert is_meaningless_empty_column_fill(move, state)


def test_ucs_cost_caps_breaking_and_meaningless_penalty_stack():
	state = State.from_lists(
		tableau=[[Card("spades", "9"), Card("hearts", "8")], []] + [[] for _ in range(6)],
		freecells=[None, None, None, None],
		foundations=[[], [], [], []],
	)

	move = Move(
		MoveType.TABLEAU_TO_TABLEAU,
		Card("hearts", "8"),
		("tableau", 0),
		("tableau", 1),
		sequence=(Card("hearts", "8"),),
	)

	assert is_breaking_stack(move, state)
	assert is_meaningless_empty_column_fill(move, state)
	assert ucs_move_cost(move, prev_state=state) == 18
