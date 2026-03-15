from backend.model.models import Card
from frontend.qt_compat import QColor, QDrag, QFont, QFrame, QMimeData, QPainter, QPen, Qt, Signal, QPixmap, QLinearGradient, QBrush, QPainterPath


SUIT_SYMBOL = {
	"hearts": "♥",
	"diamonds": "♦",
	"clubs": "♣",
	"spades": "♠",
}


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
		text = event.mimeData().text()
		parts = text.split(":")
		if len(parts) >= 2:
			from_pos = (parts[0], int(parts[1]))
			if len(parts) == 3:
				from_pos = (parts[0], int(parts[1]), int(parts[2]))
			if self.position[0] == "tableau":
				to_pos = ("tableau", self.position[1])
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
		mime = QMimeData()
		mime.setText(self._drag_source_payload)
		drag.setMimeData(mime)
		
		# Set visual pixmap for the drag
		drag_seq = getattr(self, '_drag_sequence', [])
		if not drag_seq:
			drag_seq = [self.card]

		card_h = self.height()
		offset = 30
		total_h = card_h + (len(drag_seq) - 1) * offset
		
		pixmap = QPixmap(self.width(), total_h)
		pixmap.fill(Qt.GlobalColor.transparent)
		
		painter = QPainter(pixmap)
		for i, c in enumerate(drag_seq):
			cw_pix = self._build_preview_pixmap(c, self.width(), self.height())
			if i < len(drag_seq) - 1:
				overlay = QPainter(cw_pix)
				overlay.fillRect(0, 0, cw_pix.width(), cw_pix.height(), QColor(0, 0, 0, 30))
				overlay.end()
			painter.drawPixmap(0, i * offset, cw_pix)
		painter.end()

		drag.setPixmap(pixmap)
		drag.setHotSpot(event.pos())

		self._drag_started = True
		
		# Hide the cards being dragged
		widgets_to_hide = []
		if self.parent():
			for child in self.parent().children():
				if isinstance(child, CardWidget) and hasattr(child, 'position') and len(child.position) == 3:
					if child.position[0] == self.position[0] and child.position[1] == self.position[1]:
						if child.position[2] >= self.position[2]:
							widgets_to_hide.append(child)
		if not widgets_to_hide:
			widgets_to_hide.append(self)
			
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

		# Load pixmap
		import os
		rank = self.card.rank
		if rank.isdigit() and len(rank) == 1:
			rank = f"0{rank}"
		
		# e.g. "card_clubs_02.png" or "card_hearts_A.png"
		filename = f"card_{self.card.suit}_{rank}.png"
		filepath = os.path.join("asset", "card", filename)
		
		pixmap = QPixmap(filepath)

		# Scale pixmap
		if not pixmap.isNull():
			pixmap = pixmap.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
			painter.drawPixmap(0, 0, pixmap)
		else:
			# Fallback if image not found
			painter.fillRect(0, 0, w, h, QColor(Qt.GlobalColor.white))
			painter.setPen(QColor(Qt.GlobalColor.black))
			painter.drawRect(0, 0, w - 1, h - 1)
			painter.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, f"{self.card.rank} of {self.card.suit}")

		painter.setPen(QPen(QColor(255, 255, 255, 55), 1))
		painter.setBrush(Qt.BrushStyle.NoBrush)
		painter.drawRoundedRect(0, 0, w - 1, h - 1, 8, 8)

		shadow_path = QPainterPath()
		shadow_path.addRoundedRect(1.5, h - 12.0, w - 3.0, 10.0, 5.0, 5.0)
		painter.fillPath(shadow_path, QColor(0, 0, 0, 36))

		# Draw borders based on state
		if self._selected:
			painter.setPen(QPen(QColor("#ffe366"), 3))
			painter.setBrush(Qt.BrushStyle.NoBrush)
			painter.drawRoundedRect(1, 1, w - 2, h - 2, 8, 8)
		elif self._hovered and self._drag_enabled:
			painter.setPen(QPen(QColor("#4eb9ff"), 2))
			painter.setBrush(Qt.BrushStyle.NoBrush)
			painter.drawRoundedRect(1, 1, w - 2, h - 2, 8, 8)

	@staticmethod
	def _build_preview_pixmap(card: Card, width: int, height: int) -> QPixmap:
		import os

		rank = card.rank
		if rank.isdigit() and len(rank) == 1:
			rank = f"0{rank}"

		filename = f"card_{card.suit}_{rank}.png"
		filepath = os.path.join("asset", "card", filename)

		pixmap = QPixmap(width, height)
		pixmap.fill(Qt.GlobalColor.transparent)

		painter = QPainter(pixmap)
		painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
		painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

		card_pixmap = QPixmap(filepath)
		if not card_pixmap.isNull():
			card_pixmap = card_pixmap.scaled(width, height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
			painter.drawPixmap(0, 0, card_pixmap)
		else:
			painter.fillRect(0, 0, width, height, QColor(Qt.GlobalColor.white))
			painter.setPen(QColor(Qt.GlobalColor.black))
			painter.drawRect(0, 0, width - 1, height - 1)
			painter.drawText(0, 0, width, height, Qt.AlignmentFlag.AlignCenter, f"{card.rank} {SUIT_SYMBOL.get(card.suit, '?')}")

		painter.setPen(QPen(QColor(255, 255, 255, 45), 1))
		painter.setBrush(Qt.BrushStyle.NoBrush)
		painter.drawRoundedRect(0, 0, width - 1, height - 1, 8, 8)
		painter.end()

		return pixmap

