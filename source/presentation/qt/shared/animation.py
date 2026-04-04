"""Reusable UI animations for card fade-in and movement transitions."""

from source.presentation.qt.shared.qt import QEasingCurve, QGraphicsOpacityEffect, QPropertyAnimation
from source.presentation.qt.shared.sound import play_card_drop_sound


def _play_move_sound() -> None:
    """Play card-drop sound for move animation."""
    play_card_drop_sound()


def _on_fade_finished(widget, effect):
    """Clean fade effect after animation ends to avoid stacked graphics effects."""
    try:
        if widget.graphicsEffect() is effect:
            widget.setGraphicsEffect(None)
    except RuntimeError:
        return


def fade_in(widget, duration: int = 240):
    """Animate widget opacity from 0 to 1.

    Args:
        widget: Target widget.
        duration: Animation duration in milliseconds.
    """
    old_animation = getattr(widget, "_fade_animation", None)
    if old_animation is not None:
        old_animation.stop()

    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.finished.connect(lambda w=widget, e=effect: _on_fade_finished(w, e))
    animation.start()
    widget._fade_animation = animation


def animate_move(widget, start_pos, end_pos, duration=220, play_sound: bool = True):
    """Animate widget movement between two positions.

    Args:
        widget: Target widget.
        start_pos: Starting position.
        end_pos: Ending position.
        duration: Animation duration in milliseconds.
        play_sound: Whether to play move sound for this animation.
    """
    if start_pos == end_pos:
        widget.move(end_pos)
        return

    old_animation = getattr(widget, "_move_animation", None)
    if old_animation is not None:
        old_animation.stop()

    dx = end_pos.x() - start_pos.x()
    dy = end_pos.y() - start_pos.y()
    travel = (dx * dx + dy * dy) ** 0.5
    if travel < 2:
        widget.move(end_pos)
        return

    adaptive_duration = int(max(140, min(360, duration * (0.6 + (travel / 85.0)))))
    if play_sound:
        _play_move_sound()

    animation = QPropertyAnimation(widget, b"pos", widget)
    animation.setDuration(adaptive_duration)
    animation.setStartValue(start_pos)
    animation.setEndValue(end_pos)
    animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
    animation.start()
    widget._move_animation = animation
