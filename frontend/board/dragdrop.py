def parse_drag_payload(payload: str) -> tuple | None:
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
