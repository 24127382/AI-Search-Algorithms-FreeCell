"""Shared search profile definitions for solver algorithms."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from source.domain.solver.utils.utility import (
    env_bool,
    env_float,
    env_int,
    env_zero_is_false,
)


@dataclass(frozen=True)
class BFSProfile:
    """Configuration profile for BFS behavior."""

    runtime_log_enabled: bool = True
    inner_cancel_check_interval: int = 256
    stats_update_interval: int = 32
    hard_time_cap_ms: float = 60000.0
    max_expanded_nodes: int = 1000000

    @staticmethod
    def from_env() -> "BFSProfile":
        return BFSProfile(
            runtime_log_enabled=env_zero_is_false("BFS_RUNTIME_LOG", default=True),
            inner_cancel_check_interval=env_int(
                "BFS_INNER_CANCEL_CHECK_INTERVAL", 256, minimum=1
            ),
            stats_update_interval=env_int("BFS_STATS_UPDATE_INTERVAL", 32, minimum=1),
            hard_time_cap_ms=env_float("BFS_HARD_TIME_CAP_MS", 60000.0, minimum=1.0),
            max_expanded_nodes=env_int(
                "BFS_MAX_EXPANDED_NODES", 1000000, minimum=1
            ),
        )

    @staticmethod
    def from_dict(payload: dict) -> "BFSProfile":
        defaults = BFSProfile.from_env()
        return BFSProfile(
            runtime_log_enabled=bool(
                payload.get("runtime_log_enabled", defaults.runtime_log_enabled)
            ),
            inner_cancel_check_interval=max(
                1,
                int(
                    payload.get(
                        "inner_cancel_check_interval",
                        defaults.inner_cancel_check_interval,
                    )
                ),
            ),
            stats_update_interval=max(
                1,
                int(payload.get("stats_update_interval", defaults.stats_update_interval)),
            ),
            hard_time_cap_ms=max(
                1.0,
                float(payload.get("hard_time_cap_ms", defaults.hard_time_cap_ms)),
            ),
            max_expanded_nodes=max(
                1,
                int(
                    payload.get(
                        "max_expanded_nodes",
                        defaults.max_expanded_nodes,
                    )
                ),
            ),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AStarProfile:
    """Configuration profile for A* behavior."""

    runtime_log_enabled: bool = True
    inner_cancel_check_interval: int = 256
    stats_update_interval: int = 32
    compact_min_arena_nodes: int = 4096
    compact_arena_live_ratio: int = 2

    @staticmethod
    def from_env() -> "AStarProfile":
        return AStarProfile(
            runtime_log_enabled=env_zero_is_false("ASTAR_RUNTIME_LOG", default=True),
            inner_cancel_check_interval=env_int(
                "ASTAR_INNER_CANCEL_CHECK_INTERVAL", 256, minimum=1
            ),
            stats_update_interval=env_int(
                "ASTAR_STATS_UPDATE_INTERVAL", 32, minimum=1
            ),
            compact_min_arena_nodes=env_int(
                "ASTAR_COMPACT_MIN_ARENA_NODES", 4096, minimum=1
            ),
            compact_arena_live_ratio=env_int(
                "ASTAR_COMPACT_ARENA_LIVE_RATIO", 2, minimum=1
            ),
        )

    @staticmethod
    def from_dict(payload: dict) -> "AStarProfile":
        defaults = AStarProfile.from_env()
        return AStarProfile(
            runtime_log_enabled=bool(
                payload.get("runtime_log_enabled", defaults.runtime_log_enabled)
            ),
            inner_cancel_check_interval=max(
                1,
                int(
                    payload.get(
                        "inner_cancel_check_interval",
                        defaults.inner_cancel_check_interval,
                    )
                ),
            ),
            stats_update_interval=max(
                1,
                int(payload.get("stats_update_interval", defaults.stats_update_interval)),
            ),
            compact_min_arena_nodes=max(
                1,
                int(
                    payload.get(
                        "compact_min_arena_nodes",
                        defaults.compact_min_arena_nodes,
                    )
                ),
            ),
            compact_arena_live_ratio=max(
                1,
                int(
                    payload.get(
                        "compact_arena_live_ratio",
                        defaults.compact_arena_live_ratio,
                    )
                ),
            ),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DFSProfile:
    """Configuration profile for DFS behavior."""

    runtime_log_enabled: bool = True
    inner_cancel_check_interval: int = 256
    stats_update_interval: int = 32
    hard_time_cap_ms: float = 60000.0

    @staticmethod
    def from_env() -> "DFSProfile":
        return DFSProfile(
            runtime_log_enabled=env_zero_is_false("DFS_RUNTIME_LOG", default=True),
            inner_cancel_check_interval=env_int(
                "DFS_INNER_CANCEL_CHECK_INTERVAL", 256, minimum=1
            ),
            stats_update_interval=env_int("DFS_STATS_UPDATE_INTERVAL", 32, minimum=1),
            hard_time_cap_ms=env_float("DFS_HARD_TIME_CAP_MS", 60000.0, minimum=1.0),
        )

    @staticmethod
    def from_dict(payload: dict) -> "DFSProfile":
        defaults = DFSProfile.from_env()
        return DFSProfile(
            runtime_log_enabled=bool(
                payload.get("runtime_log_enabled", defaults.runtime_log_enabled)
            ),
            inner_cancel_check_interval=max(
                1,
                int(
                    payload.get(
                        "inner_cancel_check_interval",
                        defaults.inner_cancel_check_interval,
                    )
                ),
            ),
            stats_update_interval=max(
                1,
                int(payload.get("stats_update_interval", defaults.stats_update_interval)),
            ),
            hard_time_cap_ms=max(
                1.0,
                float(payload.get("hard_time_cap_ms", defaults.hard_time_cap_ms)),
            ),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class UCSProfile:
    """Configuration profile for UCS behavior."""

    runtime_log_enabled: bool = True
    inner_cancel_check_interval: int = 256
    stats_update_interval: int = 32
    sort_candidate_moves: bool = False
    prune_safe_moves: bool = True
    prune_immediate_undo: bool = True
    prune_canonical_redundant: bool = True
    dominance_pruning_enabled: bool = True
    move_interning_enabled: bool = True

    @staticmethod
    def from_env() -> "UCSProfile":
        return UCSProfile(
            runtime_log_enabled=env_zero_is_false("UCS_RUNTIME_LOG", default=True),
            inner_cancel_check_interval=env_int(
                "UCS_INNER_CANCEL_CHECK_INTERVAL", 256, minimum=1
            ),
            stats_update_interval=env_int("UCS_STATS_UPDATE_INTERVAL", 32, minimum=1),
            sort_candidate_moves=env_bool("UCS_SORT_CANDIDATE_MOVES", False),
            prune_safe_moves=env_bool("UCS_PRUNE_SAFE_MOVES", True),
            prune_immediate_undo=env_bool("UCS_PRUNE_IMMEDIATE_UNDO", True),
            prune_canonical_redundant=env_bool(
                "UCS_PRUNE_CANONICAL_REDUNDANT", True
            ),
            dominance_pruning_enabled=env_bool(
                "UCS_DOMINANCE_PRUNING_ENABLED", True
            ),
            move_interning_enabled=env_bool("UCS_MOVE_INTERNING_ENABLED", True),
        )

    @staticmethod
    def from_dict(payload: dict) -> "UCSProfile":
        defaults = UCSProfile.from_env()
        return UCSProfile(
            runtime_log_enabled=bool(
                payload.get("runtime_log_enabled", defaults.runtime_log_enabled)
            ),
            inner_cancel_check_interval=max(
                1,
                int(
                    payload.get(
                        "inner_cancel_check_interval",
                        defaults.inner_cancel_check_interval,
                    )
                ),
            ),
            stats_update_interval=max(
                1,
                int(payload.get("stats_update_interval", defaults.stats_update_interval)),
            ),
            sort_candidate_moves=bool(
                payload.get("sort_candidate_moves", defaults.sort_candidate_moves)
            ),
            prune_safe_moves=bool(
                payload.get("prune_safe_moves", defaults.prune_safe_moves)
            ),
            prune_immediate_undo=bool(
                payload.get("prune_immediate_undo", defaults.prune_immediate_undo)
            ),
            prune_canonical_redundant=bool(
                payload.get(
                    "prune_canonical_redundant",
                    defaults.prune_canonical_redundant,
                )
            ),
            dominance_pruning_enabled=bool(
                payload.get(
                    "dominance_pruning_enabled",
                    defaults.dominance_pruning_enabled,
                )
            ),
            move_interning_enabled=bool(
                payload.get(
                    "move_interning_enabled",
                    defaults.move_interning_enabled,
                )
            ),
        )

    def to_dict(self) -> dict:
        return asdict(self)
