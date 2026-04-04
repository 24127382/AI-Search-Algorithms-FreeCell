"""Shared frontend exports for animation helpers and Qt backend alias."""

from source.presentation.qt.shared.animation import animate_move, fade_in
from source.presentation.qt.shared.qt import QT_API

__all__ = ["fade_in", "animate_move", "QT_API"]
