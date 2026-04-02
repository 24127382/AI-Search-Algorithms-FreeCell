"""Custom slot widgets for board drops and click/drag interactions."""

from frontend.board.constants import SLOT_FREECELL, SLOT_TABLEAU
from frontend.board.dragdrop import parse_drag_payload
from frontend.shared.qt import (
    QDrag,
    QGraphicsOpacityEffect,
    QMimeData,
    QPixmap,
    QPushButton,
    Qt,
    QWidget,
    Signal,
)


class SlotButton(QPushButton):
    """Interactive button that acts as a board slot and drag/drop endpoint."""

    card_clicked = Signal(tuple)
    drop_received = Signal(tuple, tuple)

    def __init__(self, slot_type: str, slot_index: int, parent=None):
        """Create slot button bound to one logical board position.

        Args:
                slot_type: Slot type label.
                slot_index: Slot index inside type group.
                parent: Optional parent widget.
        """
        super().__init__(parent)
        self.slot_type = slot_type.lower()
        self.slot_index = slot_index
        self._drag_enabled = False
        self._drag_payload = ""
        self._mouse_press_pos = None
        self._drag_started = False
        self.setAcceptDrops(True)

    def set_drag_payload(self, payload: str, enabled: bool):
        """Configure drag payload text and drag enable flag.

        Args:
                payload: Drag payload string.
                enabled: Whether dragging is enabled.
        """
        self._drag_payload = payload
        self._drag_enabled = enabled

    def mousePressEvent(self, event):
        """Store starting mouse position for drag-threshold detection."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._mouse_press_pos = event.pos()
            self._drag_started = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Start a drag operation when left-button movement exceeds threshold."""
        if not self._drag_enabled:
            super().mouseMoveEvent(event)
            return

        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return

        if self._mouse_press_pos is None:
            super().mouseMoveEvent(event)
            return

        delta = event.pos() - self._mouse_press_pos
        if delta.manhattanLength() < 10:
            super().mouseMoveEvent(event)
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self._drag_payload)
        drag.setMimeData(mime)

        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.GlobalColor.transparent)
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())

        self._drag_started = True

        should_hide = False
        if (
            self.slot_type == SLOT_FREECELL
            and self._drag_payload
            and not self._drag_payload.endswith(":False")
        ):
            should_hide = True

        if should_hide:
            effect = QGraphicsOpacityEffect(self)
            effect.setOpacity(0.0)
            self.setGraphicsEffect(effect)

        drag.exec(Qt.DropAction.MoveAction)

        if should_hide:
            try:
                self.setGraphicsEffect(None)
            except RuntimeError:
                pass

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Emit card-click when release occurs without initiating a drag."""
        if event.button() == Qt.MouseButton.LeftButton and not self._drag_started:
            source = (self.slot_type, self.slot_index)
            if self.slot_type in (SLOT_TABLEAU, SLOT_FREECELL):
                self.card_clicked.emit(source)
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        """Accept drag events that carry expected text payload format."""
        if event.mimeData().hasText() and ":" in event.mimeData().text():
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event):
        """Parse source payload and emit a normalized drop event."""
        from_pos = parse_drag_payload(event.mimeData().text())
        if from_pos is None:
            event.ignore()
            return

        to_pos = (self.slot_type, self.slot_index)
        self.drop_received.emit(from_pos, to_pos)
        event.acceptProposedAction()


class TableauColumnWidget(QWidget):
    """Container widget representing one tableau column drop area."""

    drop_received = Signal(tuple, tuple)

    def __init__(self, col_idx: int, parent=None):
        """Initialize drop target for specific tableau column index.

        Args:
                col_idx: Tableau column index.
                parent: Optional parent widget.
        """
        super().__init__(parent)
        self.col_idx = col_idx
        self.setAcceptDrops(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def dragEnterEvent(self, event):
        """Accept drag events that carry expected text payload format."""
        if event.mimeData().hasText() and ":" in event.mimeData().text():
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event):
        """Emit drop event mapping source payload into this tableau column."""
        from_pos = parse_drag_payload(event.mimeData().text())
        if from_pos is None:
            event.ignore()
            return

        to_pos = (SLOT_TABLEAU, self.col_idx)
        self.drop_received.emit(from_pos, to_pos)
        event.acceptProposedAction()
