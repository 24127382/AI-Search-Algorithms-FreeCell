"""Painting helpers for card faces and interactive overlays."""

from frontend.card.assets import card_asset_path
from frontend.shared.qt import QColor, QPainterPath, QPen, QPixmap, Qt


def paint_card_face(painter, card, width: int, height: int):
    """Draw card image, or fallback text card when asset is unavailable.

    Args:
            painter: Active Qt painter.
            card: Card model instance.
            width: Target card width.
            height: Target card height.
    """
    pixmap = QPixmap(card_asset_path(card))
    if not pixmap.isNull():
        pixmap = pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(0, 0, pixmap)
        return

    painter.fillRect(0, 0, width, height, QColor(Qt.GlobalColor.white))
    painter.setPen(QColor(Qt.GlobalColor.black))
    painter.drawRect(0, 0, width - 1, height - 1)
    painter.drawText(
        0, 0, width, height, Qt.AlignmentFlag.AlignCenter, f"{card.rank} of {card.suit}"
    )


def paint_card_overlay(
    painter, width: int, height: int, selected: bool, hovered: bool, drag_enabled: bool
):
    """Draw border/shadow/selection overlays above card face.

    Args:
            painter: Active Qt painter.
            width: Card width.
            height: Card height.
            selected: Whether card is selected.
            hovered: Whether pointer is hovering card.
            drag_enabled: Whether card is draggable.
    """
    overlay_inset_x = 7
    overlay_inset_y = 0
    overlay_w = max(1, width - 1 - (overlay_inset_x * 2))
    overlay_h = max(1, height - 1 - (overlay_inset_y * 2))

    painter.setPen(QPen(QColor(255, 255, 255, 55), 1))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(
        overlay_inset_x, overlay_inset_y, overlay_w, overlay_h, 8, 8
    )

    shadow_path = QPainterPath()
    shadow_path.addRoundedRect(
        overlay_inset_x + 1.5,
        height - 12.0,
        max(1.0, width - 3.0 - (overlay_inset_x * 2)),
        10.0,
        5.0,
        5.0,
    )
    painter.fillPath(shadow_path, QColor(0, 0, 0, 36))

    if selected:
        painter.setPen(QPen(QColor("#ffe366"), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            overlay_inset_x + 1,
            overlay_inset_y + 1,
            max(1, overlay_w - 1),
            max(1, overlay_h - 1),
            8,
            8,
        )
    elif hovered and drag_enabled:
        painter.setPen(QPen(QColor("#4eb9ff"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            overlay_inset_x + 1,
            overlay_inset_y + 1,
            max(1, overlay_w - 1),
            max(1, overlay_h - 1),
            8,
            8,
        )
