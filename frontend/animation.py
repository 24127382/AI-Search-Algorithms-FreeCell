from frontend.qt_compat import QEasingCurve, QGraphicsOpacityEffect, QPropertyAnimation

def fade_in(widget, duration: int = 180):
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b'opacity', widget)
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.start()
    widget._fade_animation = animation

def animate_move(widget, start_pos, end_pos, duration=250):
    animation = QPropertyAnimation(widget, b'pos', widget)
    animation.setDuration(duration)
    animation.setStartValue(start_pos)
    animation.setEndValue(end_pos)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.start()
    widget._move_animation = animation
