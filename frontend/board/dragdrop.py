"""Helpers for encoding and parsing lightweight board drag payloads."""


def parse_drag_payload(payload: str) -> tuple | None:
    """Parse drag payload into position tuple.

    Args:
            payload: Drag payload text.

    Returns:
            tuple | None: `(slot_type, index[, card_index])` or `None` when invalid.
    """
    parts = payload.split(":")
    if len(parts) < 2:
        return None

    try:
        base = (parts[0].lower(), int(parts[1]))
        if len(parts) == 3:
            return (parts[0].lower(), int(parts[1]), int(parts[2]))
        return base
    except ValueError:
        return None
