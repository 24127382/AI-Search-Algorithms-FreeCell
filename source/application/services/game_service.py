"""Application service that wraps gameplay engine operations for the UI."""

from __future__ import annotations

from typing import Optional

from source.application.engine.engine import apply_move, get_valid_moves
from source.application.engine.shuffle import deal_by_game_number, random_deal_number
from source.domain.model.state import State


class GameService:
    """Facade used by presentation layer to avoid direct engine imports."""

    @staticmethod
    def random_deal_number() -> int:
        return random_deal_number()

    @staticmethod
    def deal_by_game_number(deal_number: int):
        return deal_by_game_number(deal_number)

    @staticmethod
    def build_initial_state(deal_number: Optional[int] = None) -> tuple[int, State]:
        chosen_deal = deal_number if deal_number is not None else random_deal_number()
        tableau = deal_by_game_number(chosen_deal)
        state = State.from_lists(
            tableau=tableau,
            freecells=[None] * 4,
            foundations=[[] for _ in range(4)],
        )
        return chosen_deal, state

    @staticmethod
    def get_valid_moves(
        state: State,
        prune_safe: bool = True,
        last_move=None,
        prune_canonical_redundant: bool = False,
    ) -> list:
        return get_valid_moves(
            state,
            prune_safe=prune_safe,
            last_move=last_move,
            prune_canonical_redundant=prune_canonical_redundant,
        )

    @staticmethod
    def apply_move(state: State, move, collapse_forced: bool = False) -> State:
        return apply_move(state, move, collapse_forced=collapse_forced)
