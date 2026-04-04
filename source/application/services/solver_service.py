"""Application service that wraps solver orchestration for presentation layer."""

from __future__ import annotations

from typing import Callable

from source.domain.solver.algorithms import SUPPORTED_SOLVER_ALGORITHMS, SearchAlgorithm


class SolverService:
    """Thin facade over SearchAlgorithm to keep presentation layer decoupled."""

    def __init__(self, game_state, should_cancel: Callable[[], bool] | None = None):
        self._search_algorithm = SearchAlgorithm(
            game_state,
            should_cancel=should_cancel,
        )

    @classmethod
    def supported_algorithms(cls) -> tuple[str, ...]:
        return SUPPORTED_SOLVER_ALGORITHMS

    def search(self, algorithm: str):
        return self._search_algorithm.search(algorithm)
