from source.application.experiments.solver_stats import SolverStats
from source.domain.model.card import VALID_RANK, VALID_SUITS, Card
from source.domain.model.state import State
from source.domain.solver.bfs import BFSAlgorithm
from source.domain.solver.dfs import DFSAlgorithm


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


def test_bfs_format_last_run_stats_before_search():
    solver = BFSAlgorithm(_build_near_goal_state())
    report = SolverStats.format_bfs(solver.last_run_stats)

    assert report == "No BFS stats available. Run search() first."


def test_dfs_format_last_run_stats_before_search():
    solver = DFSAlgorithm(_build_near_goal_state())
    report = SolverStats.format_dfs(solver.last_run_stats)

    assert report == "No DFS stats available. Run search() first."


def test_bfs_format_last_run_stats_after_search_contains_core_metrics():
    solver = BFSAlgorithm(_build_near_goal_state())

    path = solver.search()
    report = SolverStats.format_bfs(solver.last_run_stats)

    assert path is not None
    assert "BFS Run Stats" in report
    assert "solution_found:" in report
    assert "elapsed_ms:" in report
    assert "expanded_nodes:" in report
    assert "effective_branching_factor:" in report


def test_dfs_format_last_run_stats_after_search_contains_core_metrics():
    solver = DFSAlgorithm(_build_near_goal_state())

    path = solver.search()
    report = SolverStats.format_dfs(solver.last_run_stats)

    assert path is not None
    assert "DFS Run Stats" in report
    assert "solution_found:" in report
    assert "elapsed_ms:" in report
    assert "expanded_nodes:" in report
    assert "effective_branching_factor:" in report


def test_dfs_legacy_metric_fields_synced_from_last_run_stats():
    solver = DFSAlgorithm(_build_near_goal_state())

    solver.search()
    stats = solver.last_run_stats

    assert stats is not None
    assert solver.expanded_nodes == stats.get("expanded_nodes")
    assert solver.peak_stack_size == stats.get("peak_frontier_size")
    assert solver.execution_time_ms == stats.get("elapsed_ms")
