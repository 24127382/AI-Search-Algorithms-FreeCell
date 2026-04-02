"""Shared search profile definitions for solver algorithms."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from backend.solver.utils.utility import env_bool, env_float, env_int, env_zero_is_false


@dataclass(frozen=True)
class DFSProfile:
    """Configuration profile for DFS behavior."""

    k_cycle_steps: int = 8
    progressive_widening: bool = False
    widen_start_depth: int = 40
    widen_base_width: int = 64
    widen_growth: float = 0.20
    move_canonicalization: bool = False
    delayed_duplicate_detection: bool = False
    delayed_duplicate_batch_size: int = 64

    @staticmethod
    def from_env() -> "DFSProfile":
        return DFSProfile(
            k_cycle_steps=env_int("DFS_K_CYCLE_STEPS", 8, minimum=0),
            progressive_widening=env_bool("DFS_PROGRESSIVE_WIDENING", False),
            widen_start_depth=env_int("DFS_WIDEN_START_DEPTH", 40, minimum=0),
            widen_base_width=env_int("DFS_WIDEN_BASE_WIDTH", 64, minimum=1),
            widen_growth=env_float("DFS_WIDEN_GROWTH", 0.20, minimum=0.0),
            move_canonicalization=env_bool("DFS_MOVE_CANONICALIZATION", False),
            delayed_duplicate_detection=env_bool("DFS_DELAYED_DUPLICATE", False),
            delayed_duplicate_batch_size=env_int(
                "DFS_DELAYED_DUPLICATE_BATCH", 64, minimum=1
            ),
        )

    @staticmethod
    def from_dict(payload: dict) -> "DFSProfile":
        defaults = DFSProfile.from_env()
        return DFSProfile(
            k_cycle_steps=max(
                0, int(payload.get("k_cycle_steps", defaults.k_cycle_steps))
            ),
            progressive_widening=bool(
                payload.get("progressive_widening", defaults.progressive_widening)
            ),
            widen_start_depth=max(
                0, int(payload.get("widen_start_depth", defaults.widen_start_depth))
            ),
            widen_base_width=max(
                1, int(payload.get("widen_base_width", defaults.widen_base_width))
            ),
            widen_growth=max(
                0.0, float(payload.get("widen_growth", defaults.widen_growth))
            ),
            move_canonicalization=bool(
                payload.get("move_canonicalization", defaults.move_canonicalization)
            ),
            delayed_duplicate_detection=bool(
                payload.get(
                    "delayed_duplicate_detection", defaults.delayed_duplicate_detection
                )
            ),
            delayed_duplicate_batch_size=max(
                1,
                int(
                    payload.get(
                        "delayed_duplicate_batch_size",
                        defaults.delayed_duplicate_batch_size,
                    )
                ),
            ),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class UCSProfile:
    """Configuration profile for UCS behavior."""

    runtime_log_enabled: bool = True

    @staticmethod
    def from_env() -> "UCSProfile":
        return UCSProfile(
            runtime_log_enabled=env_zero_is_false("UCS_RUNTIME_LOG", default=True)
        )

    @staticmethod
    def from_dict(payload: dict) -> "UCSProfile":
        defaults = UCSProfile.from_env()
        return UCSProfile(
            runtime_log_enabled=bool(
                payload.get("runtime_log_enabled", defaults.runtime_log_enabled)
            )
        )

    def to_dict(self) -> dict:
        return asdict(self)
