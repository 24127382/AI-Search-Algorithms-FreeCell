"""Qt compatibility layer for running with PySide6 or PyQt6."""

try:
    from PySide6.QtCore import Qt, Signal, QMimeData, QPropertyAnimation, QEasingCurve, QTimer, QThread
    from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QLinearGradient, QBrush, QPainterPath, QAction
    from PySide6.QtGui import QDrag
    from PySide6.QtWidgets import (
        QApplication,
        QDialog,
        QFrame,
        QGraphicsOpacityEffect,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )

    QT_API = "PySide6"
except ImportError:
    from PyQt6.QtCore import Qt, QMimeData, QPropertyAnimation, QEasingCurve, QTimer, QThread, pyqtSignal as Signal
    from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QLinearGradient, QBrush, QPainterPath, QAction
    from PyQt6.QtGui import QDrag
    from PyQt6.QtWidgets import (
        QApplication,
        QDialog,
        QFrame,
        QGraphicsOpacityEffect,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )

    QT_API = "PyQt6"
