from source.application.experiments.solver_stats import SolverStats
from source.application.services.game_service import GameService
from source.domain.solver.dfs import DFSAlgorithm
from source.domain.solver.search_utils.search_profile import DFSProfile


def test_dfs_simple_profile_deal_155_stats_report():

    deal_number, initial_state = GameService.build_initial_state(deal_number=10)
    profile = DFSProfile(hard_time_cap_ms=20000.0)
    solver = DFSAlgorithm(
        initial_state,
        profile=profile,
        runtime_log_enabled=False,
    )

    path = solver.search()
    stats = solver.last_run_stats

    assert deal_number == 10
    assert stats is not None
    assert stats["stop_reason"] in {
        "hard_time_cap",
        "solved",
        "exhausted",
    }

    report = SolverStats.format_dfs(stats)
    print(f"\n[DFS simple profile | deal {deal_number}]")
    print(report)

    assert stats["solution_found"] == (path is not None)
    if path is not None:
        assert len(path) == stats["solution_length"]