"""Qt compatibility layer for running with PySide6 or PyQt6."""

try:
    from PySide6.QtCore import Qt, Signal, QMimeData, QPropertyAnimation, QEasingCurve
    from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QLinearGradient, QBrush, QPainterPath
    from PySide6.QtGui import QDrag
    from PySide6.QtWidgets import (
        QApplication,
        QFrame,
        QGraphicsOpacityEffect,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )

    QT_API = "PySide6"
except ImportError:
    from PyQt6.QtCore import Qt, QMimeData, QPropertyAnimation, QEasingCurve, pyqtSignal as Signal
    from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QLinearGradient, QBrush, QPainterPath
    from PyQt6.QtGui import QDrag
    from PyQt6.QtWidgets import (
        QApplication,
        QFrame,
        QGraphicsOpacityEffect,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )

    QT_API = "PyQt6"
