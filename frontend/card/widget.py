from backend.model.models import Card
from frontend.card.assets import SUIT_SYMBOL
from frontend.card.drag import (
	build_drag_mime,
	build_preview_pixmap,
	build_stacked_drag_pixmap,
	collect_dragged_widgets,
	parse_drop_position,
)
from frontend.card.paint import paint_card_face, paint_card_overlay
from frontend.shared.qt import QDrag, QFrame, QPainter, QPixmap, Qt, Signal


class CardWidget(QFrame):
	clicked = Signal(tuple)
	double_clicked = Signal(tuple)
	drop_received = Signal(tuple, tuple)

	def __init__(self, card: Card, position: tuple, parent=None):
		super().__init__(parent)
		self.card = card
		self.position = position
		self._selected = False
		self._drag_enabled = False
		self._drag_source_payload = ""
		self._drag_sequence = []
		self._mouse_press_pos = None
		self._drag_started = False
		self._hovered = False

		self.setFixedSize(64, 86)
		self.setCursor(Qt.CursorShape.PointingHandCursor)
		self.setMouseTracking(True)

	def set_selected(self, selected: bool):
		self._selected = selected
		self.update()

	def set_drag_payload(self, payload: str, enabled: bool, drag_sequence=None):
		self._drag_source_payload = payload
		self._drag_enabled = enabled
		self._drag_sequence = drag_sequence or []
		self.update()

	def enterEvent(self, event):
		if self._drag_enabled:
			self._hovered = True
			self.update()
		super().enterEvent(event)

	def leaveEvent(self, event):
		self._hovered = False
		self.update()
		super().leaveEvent(event)

	def mouseDoubleClickEvent(self, event):
		if event.button() == Qt.MouseButton.LeftButton:
			self.double_clicked.emit(self.position)
		super().mouseDoubleClickEvent(event)

	def dragEnterEvent(self, event):
		if event.mimeData().hasText() and ":" in event.mimeData().text():
			event.acceptProposedAction()
			return
		event.ignore()

	def dropEvent(self, event):
		from_pos, to_pos = parse_drop_position(event.mimeData().text(), self.position)
		if from_pos is not None and to_pos is not None:
			self.drop_received.emit(from_pos, to_pos)
			event.acceptProposedAction()
			return
		event.ignore()

	def mousePressEvent(self, event):
		if event.button() == Qt.MouseButton.LeftButton:
			self._mouse_press_pos = event.pos()
			self._drag_started = False
		super().mousePressEvent(event)

	def mouseMoveEvent(self, event):
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
		drag.setMimeData(build_drag_mime(self._drag_source_payload))
		drag.setPixmap(build_stacked_drag_pixmap(self, self._drag_sequence))
		drag.setHotSpot(event.pos())

		self._drag_started = True

		widgets_to_hide = collect_dragged_widgets(self)

		for w in widgets_to_hide:
			try:
				w.hide()
			except RuntimeError:
				pass

		drag.exec(Qt.DropAction.MoveAction)

		for w in widgets_to_hide:
			try:
				if getattr(w, "parent", None) and w.parent() is not None:
					w.show()
			except RuntimeError:
				pass

		super().mouseMoveEvent(event)

	def mouseReleaseEvent(self, event):
		if event.button() == Qt.MouseButton.LeftButton and not self._drag_started:
			self.clicked.emit(self.position)
		super().mouseReleaseEvent(event)

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
		painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

		w = self.width()
		h = self.height()
		paint_card_face(painter, self.card, w, h)
		paint_card_overlay(painter, w, h, self._selected, self._hovered, self._drag_enabled)

	@staticmethod
	def _build_preview_pixmap(card: Card, width: int, height: int) -> QPixmap:
		return build_preview_pixmap(card, width, height)
