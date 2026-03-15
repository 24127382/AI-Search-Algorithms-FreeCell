from frontend.card.assets import card_asset_path
from frontend.shared.qt import QColor, QPainterPath, QPen, QPixmap, Qt


def paint_card_face(painter, card, width: int, height: int):
	pixmap = QPixmap(card_asset_path(card))
	if not pixmap.isNull():
		pixmap = pixmap.scaled(width, height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
		painter.drawPixmap(0, 0, pixmap)
		return

	painter.fillRect(0, 0, width, height, QColor(Qt.GlobalColor.white))
	painter.setPen(QColor(Qt.GlobalColor.black))
	painter.drawRect(0, 0, width - 1, height - 1)
	painter.drawText(0, 0, width, height, Qt.AlignmentFlag.AlignCenter, f"{card.rank} of {card.suit}")


def paint_card_overlay(painter, width: int, height: int, selected: bool, hovered: bool, drag_enabled: bool):
	painter.setPen(QPen(QColor(255, 255, 255, 55), 1))
	painter.setBrush(Qt.BrushStyle.NoBrush)
	painter.drawRoundedRect(0, 0, width - 1, height - 1, 8, 8)

	shadow_path = QPainterPath()
	shadow_path.addRoundedRect(1.5, height - 12.0, width - 3.0, 10.0, 5.0, 5.0)
	painter.fillPath(shadow_path, QColor(0, 0, 0, 36))

	if selected:
		painter.setPen(QPen(QColor("#ffe366"), 3))
		painter.setBrush(Qt.BrushStyle.NoBrush)
		painter.drawRoundedRect(1, 1, width - 2, height - 2, 8, 8)
	elif hovered and drag_enabled:
		painter.setPen(QPen(QColor("#4eb9ff"), 2))
		painter.setBrush(Qt.BrushStyle.NoBrush)
		painter.drawRoundedRect(1, 1, width - 2, height - 2, 8, 8)
