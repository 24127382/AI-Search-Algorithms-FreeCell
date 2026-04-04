"""Unified solver utility helpers.

This module centralizes common helpers used by search algorithms:
- environment parsing
- structural priority bias
- canonical state keys
- re-exported Zobrist helpers
"""

from __future__ import annotations

import os

from source.domain.solver.utils.zobrist import (
    ZobristHash,
    ZobristTable,
    ZobristTranscoder,
    get_zobrist_table,
    zobrist_hash_state,
)

_FALSE_VALUES = {"0", "false", "no", "off"}


def env_zero_is_false(name: str, default: bool = True) -> bool:
    """Return False only when env value is exactly "0"."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw != "0"


def env_bool(name: str, default: bool) -> bool:
    """Parse bool env with permissive false tokens."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in _FALSE_VALUES


def env_int(name: str, default: int, minimum: int = 0) -> int:
    """Parse int env with fallback and lower bound."""
    raw = os.environ.get(name)
    if raw is None:
        return max(default, minimum)
    try:
        return max(int(raw), minimum)
    except ValueError:
        return max(default, minimum)


def env_float(name: str, default: float, minimum: float = 0.0) -> float:
    """Parse float env with fallback and lower bound."""
    raw = os.environ.get(name)
    if raw is None:
        return max(default, minimum)
    try:
        return max(float(raw), minimum)
    except ValueError:
        return max(default, minimum)


_ASTAR_DEFAULT_WEIGHT = env_float("ASTAR_WEIGHT", 5.0, minimum=0.0)
_PRIORITY_FOUNDATION_WEIGHT = env_int(
    "SEARCH_PRIORITY_FOUNDATION_WEIGHT", 16, minimum=0
)
_PRIORITY_EMPTY_TABLEAU_WEIGHT = env_int(
    "SEARCH_PRIORITY_EMPTY_TABLEAU_WEIGHT", 3, minimum=0
)
_PRIORITY_OCCUPIED_FREECELL_PENALTY = env_int(
    "SEARCH_PRIORITY_OCCUPIED_FREECELL_PENALTY", 1, minimum=0
)


def astar_default_weight() -> float:
    """Return configured default A* heuristic inflation weight."""
    return _ASTAR_DEFAULT_WEIGHT


def structural_priority_bias(state) -> int:
    """Compute tie-break bias where lower values are prioritized."""
    foundation_bits = state.foundation_bits
    foundation_total = (
        (foundation_bits & 0xF)
        + ((foundation_bits >> 4) & 0xF)
        + ((foundation_bits >> 8) & 0xF)
        + ((foundation_bits >> 12) & 0xF)
    )
    empty_tableau = sum(1 for column in state.tableau if not column)
    occupied_freecells = sum(1 for card in state.freecells if card is not None)
    progress_score = (
        (foundation_total * _PRIORITY_FOUNDATION_WEIGHT)
        + (empty_tableau * _PRIORITY_EMPTY_TABLEAU_WEIGHT)
        - (occupied_freecells * _PRIORITY_OCCUPIED_FREECELL_PENALTY)
    )
    return -progress_score


def state_key(state) -> int:
    """Return canonical key for visited/dominance maps."""
    return getattr(state, "board_code", hash(state))


def state_id(state) -> int:
    """Return compact stable identifier for pooled structures."""
    board_code = getattr(state, "board_code", None)
    if board_code is not None:
        return board_code

    legacy_board_code = getattr(state, "_board_code", None)
    if legacy_board_code is not None:
        return legacy_board_code

    legacy_board_int = getattr(state, "_board_int", None)
    if legacy_board_int is not None:
        return legacy_board_int

    return hash(state)
