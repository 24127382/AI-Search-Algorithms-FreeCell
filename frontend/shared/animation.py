from frontend.shared.qt import QEasingCurve, QGraphicsOpacityEffect, QPropertyAnimation


def fade_in(widget, duration: int = 180):
    """Animate widget opacity from 0 to 1."""
    old_animation = getattr(widget, "_fade_animation", None)
    if old_animation is not None:
        old_animation.stop()

    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutSine)
    animation.start()
    widget._fade_animation = animation


def animate_move(widget, start_pos, end_pos, duration=170):
    """Animate widget movement between two positions."""
    old_animation = getattr(widget, "_move_animation", None)
    if old_animation is not None:
        old_animation.stop()

    animation = QPropertyAnimation(widget, b"pos", widget)
    animation.setDuration(duration)
    animation.setStartValue(start_pos)
    animation.setEndValue(end_pos)
    animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
    animation.start()
    widget._move_animation = animation
