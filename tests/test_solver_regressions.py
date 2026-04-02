from backend.engine.engine import apply_move, get_valid_moves
from backend.model.card import VALID_RANK, VALID_SUITS, Card
from backend.model.move import MoveType
from backend.model.state import State
from backend.solver.astar import AStarAlgorithm
from backend.solver.bfs import BFSAlgorithm
from backend.solver.search_utils.ucs_utils import ucs_move_cost
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


def _build_symmetry_state() -> State:
    return State.from_lists(
        tableau=[
            [Card(suit="hearts", rank="K")],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
        ],
        freecells=[Card(suit="clubs", rank="Q"), None, None, None],
        foundations=[[], [], [], []],
    )


def test_ucs_foundation_cost_is_non_negative():
    state = _build_near_goal_state()
    moves = get_valid_moves(state)

    foundation_move = next(move for move in moves if move.to_pos[0] == "foundation")
    next_state = apply_move(state, foundation_move)
    cost = ucs_move_cost(foundation_move, prev_state=state, next_state=next_state)

    assert cost >= 0


def test_bfs_cancelled_run_finalizes_stats():
    solver = BFSAlgorithm(_build_near_goal_state(), should_cancel=lambda: True)

    result = solver.search()

    assert result is None
    assert solver.last_run_stats is not None
    assert solver.last_run_stats["stop_reason"] == "cancelled"
    assert solver.last_run_stats["solution_found"] is False


def test_ucs_cancelled_run_finalizes_stats():
    solver = UCSAlgorithm(_build_near_goal_state(), should_cancel=lambda: True)

    result = solver.search()

    assert result is None
    assert solver.last_run_stats is not None
    assert solver.last_run_stats["stop_reason"] == "cancelled"
    assert solver.last_run_stats["solution_found"] is False


def test_astar_cancelled_run_finalizes_stats():
    solver = AStarAlgorithm(_build_near_goal_state(), should_cancel=lambda: True)

    result = solver.search()

    assert result is None
    assert solver.last_run_stats is not None
    assert solver.last_run_stats["stop_reason"] == "cancelled"
    assert solver.last_run_stats["solution_found"] is False


def test_astar_stats_include_reopen_and_compaction_metrics():
    solver = AStarAlgorithm(_build_near_goal_state())

    path = solver.search()

    assert path is not None
    assert solver.last_run_stats is not None
    assert "reopened_nodes" in solver.last_run_stats
    assert "arena_compactions" in solver.last_run_stats
    assert "arena_nodes_reclaimed" in solver.last_run_stats


def test_solver_move_pruning_removes_freecell_symmetry():
    state = _build_symmetry_state()

    baseline_moves = get_valid_moves(
        state,
        prune_safe=False,
        prune_canonical_redundant=False,
    )
    pruned_moves = get_valid_moves(
        state,
        prune_safe=False,
        prune_canonical_redundant=True,
    )

    baseline_freecell_to_freecell = [
        move
        for move in baseline_moves
        if move.move_type == MoveType.FREECELL_TO_FREECELL
    ]
    pruned_freecell_to_freecell = [
        move for move in pruned_moves if move.move_type == MoveType.FREECELL_TO_FREECELL
    ]

    assert baseline_freecell_to_freecell
    assert not pruned_freecell_to_freecell

    baseline_empty_tableau_targets = [
        move
        for move in baseline_moves
        if move.from_pos == ("freecell", 0)
        and move.to_pos[0] == "tableau"
        and not state.tableau[move.to_pos[1]]
    ]
    pruned_empty_tableau_targets = [
        move
        for move in pruned_moves
        if move.from_pos == ("freecell", 0)
        and move.to_pos[0] == "tableau"
        and not state.tableau[move.to_pos[1]]
    ]

    assert len(baseline_empty_tableau_targets) > 1
    assert len(pruned_empty_tableau_targets) == 1
