from frontend.card.assets import SUIT_SYMBOL, card_asset_path
from frontend.shared.qt import QColor, QMimeData, QPainter, QPixmap, Qt


def parse_drop_position(payload: str, target_position: tuple) -> tuple[tuple | None, tuple | None]:
	parts = payload.split(":")
	if len(parts) < 2:
		return None, None

	try:
		from_pos = (parts[0], int(parts[1]))
		if len(parts) == 3:
			from_pos = (parts[0], int(parts[1]), int(parts[2]))
	except ValueError:
		return None, None

	if target_position[0] != "tableau":
		return None, None
	to_pos = ("tableau", target_position[1])
	return from_pos, to_pos


def build_drag_mime(payload: str) -> QMimeData:
	mime = QMimeData()
	mime.setText(payload)
	return mime


def build_preview_pixmap(card, width: int, height: int) -> QPixmap:
	pixmap = QPixmap(width, height)
	pixmap.fill(Qt.GlobalColor.transparent)

	painter = QPainter(pixmap)
	painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
	painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

	card_pixmap = QPixmap(card_asset_path(card))
	if not card_pixmap.isNull():
		card_pixmap = card_pixmap.scaled(width, height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
		painter.drawPixmap(0, 0, card_pixmap)
	else:
		painter.fillRect(0, 0, width, height, QColor(Qt.GlobalColor.white))
		painter.setPen(QColor(Qt.GlobalColor.black))
		painter.drawRect(0, 0, width - 1, height - 1)
		painter.drawText(0, 0, width, height, Qt.AlignmentFlag.AlignCenter, f"{card.rank} {SUIT_SYMBOL.get(card.suit, '?')}")

	painter.setPen(QColor(255, 255, 255, 45))
	painter.setBrush(Qt.BrushStyle.NoBrush)
	painter.drawRoundedRect(0, 0, width - 1, height - 1, 8, 8)
	painter.end()

	return pixmap


def build_stacked_drag_pixmap(card_widget, drag_sequence: list, offset: int = 30) -> QPixmap:
	cards = drag_sequence or [card_widget.card]
	card_height = card_widget.height()
	total_height = card_height + (len(cards) - 1) * offset

	pixmap = QPixmap(card_widget.width(), total_height)
	pixmap.fill(Qt.GlobalColor.transparent)

	painter = QPainter(pixmap)
	for index, card in enumerate(cards):
		preview = build_preview_pixmap(card, card_widget.width(), card_widget.height())
		if index < len(cards) - 1:
			overlay = QPainter(preview)
			overlay.fillRect(0, 0, preview.width(), preview.height(), QColor(0, 0, 0, 30))
			overlay.end()
		painter.drawPixmap(0, index * offset, preview)
	painter.end()

	return pixmap


def collect_dragged_widgets(card_widget) -> list:
	widgets = []
	parent = card_widget.parent()
	if parent is not None:
		for child in parent.children():
			if not hasattr(child, "position"):
				continue
			if not isinstance(getattr(child, "position", None), tuple) or len(child.position) != 3:
				continue
			if child.position[0] == card_widget.position[0] and child.position[1] == card_widget.position[1]:
				if child.position[2] >= card_widget.position[2]:
					widgets.append(child)
	if not widgets:
		widgets.append(card_widget)
	return widgets
