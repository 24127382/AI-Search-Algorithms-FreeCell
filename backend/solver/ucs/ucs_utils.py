"""Utility structures and helpers used by the UCS implementation."""

from heapq import nsmallest
from typing import Dict, Iterable, List, Tuple


class BloomFilter:
	"""Simple integer bloom filter used for optional state pre-pruning."""

	def __init__(self, bit_count: int, hash_count: int):
		"""Allocate bloom bitset and choose hash probe count.

		Args:
			bit_count: Number of bits in filter.
			hash_count: Number of hash probes per item.
		"""
		self.bit_count = max(1024, int(bit_count))
		self.hash_count = max(2, int(hash_count))
		self._bytes = bytearray((self.bit_count + 7) // 8)

	def _indexes(self, value: int):
		"""Yield bloom bit indexes for a value.

		Args:
			value: Integer key to hash.
		"""
		mask = self.bit_count - 1 if (self.bit_count & (self.bit_count - 1)) == 0 else None
		for salt in range(self.hash_count):
			h = hash((value, salt * 0x9E3779B1))
			if h < 0:
				h = -h
			idx = (h & mask) if mask is not None else (h % self.bit_count)
			yield idx

	def add(self, value: int):
		"""Insert one integer key into the bloom filter.

		Args:
			value: Integer key to insert.
		"""
		for idx in self._indexes(value):
			self._bytes[idx >> 3] |= (1 << (idx & 7))

	def maybe_contains(self, value: int) -> bool:
		"""Check probable membership for an integer key.

		Args:
			value: Integer key to test.

		Returns:
			bool: `False` means definitely absent, `True` means possibly present.
		"""
		for idx in self._indexes(value):
			if not (self._bytes[idx >> 3] & (1 << (idx & 7))):
				return False
		return True


def state_id(state):
	"""Return stable compact identifier for a state object.

	Args:
		state: State-like object.

	Returns:
		int: Stable state identifier.
	"""
	board_code = getattr(state, "board_code", None)
	if board_code is not None:
		return board_code

	legacy_board_code = getattr(state, "_board_code", None)
	if legacy_board_code is not None:
		return legacy_board_code

	legacy_board_int = getattr(state, "_board_int", None)
	if legacy_board_int is not None:
		return legacy_board_int

	return hash(state)


def ucs_move_cost(move):
	"""Compute UCS edge cost for one move.

	Args:
		move: Move object.

	Returns:
		int: Edge cost used by UCS.
	"""
	if move.to_pos[0] == "foundation":
		return 1
	if move.from_pos[0] == "freecell" and move.to_pos[0] == "tableau":
		return 2
	if move.from_pos[0] == "tableau" and move.to_pos[0] == "tableau":
		return 3
	if move.to_pos[0] == "freecell":
		return 4
	return 3


def move_signature(move) -> Tuple[str, int, str, int, str, int, Tuple[int, ...]]:
	"""Build hashable signature for move interning.

	Args:
		move: Move object to encode.

	Returns:
		Tuple[str, int, str, int, str, int, Tuple[int, ...]]: Stable signature.
	"""
	sequence_ids = tuple(card.to_int() for card in (move.sequence or (move.card,)))
	return (
		move.move_type.value,
		move.card.to_int(),
		move.from_pos[0],
		move.from_pos[1],
		move.to_pos[0],
		move.to_pos[1],
		sequence_ids,
	)


def intern_move(move, move_index_by_signature: Dict[Tuple[str, int, str, int, str, int, Tuple[int, ...]], int], move_pool: List[object]) -> int:
	"""Intern move and return integer identifier.

	Args:
		move: Move object to intern.
		move_index_by_signature: Signature-to-id mapping.
		move_pool: Move pool indexed by id.

	Returns:
		int: Interned move id.
	"""
	signature = move_signature(move)
	existing_id = move_index_by_signature.get(signature)
	if existing_id is not None:
		return existing_id

	move_id = len(move_pool)
	move_pool.append(move)
	move_index_by_signature[signature] = move_id
	return move_id


def encode_edge_moves(edge_moves: Iterable[object], move_index_by_signature: Dict[Tuple[str, int, str, int, str, int, Tuple[int, ...]], int], move_pool: List[object]) -> Tuple[int, ...]:
	"""Convert edge move objects into interned id tuple.

	Args:
		edge_moves: Iterable of edge move objects.
		move_index_by_signature: Signature-to-id mapping.
		move_pool: Move pool indexed by id.

	Returns:
		Tuple[int, ...]: Interned edge move ids.
	"""
	return tuple(intern_move(move, move_index_by_signature, move_pool) for move in edge_moves)


def decode_edge_moves(edge_move_ids: Tuple[int, ...], move_pool: List[object]) -> Tuple[object, ...]:
	"""Decode interned edge ids back into move objects.

	Args:
		edge_move_ids: Tuple of interned move ids.
		move_pool: Move pool indexed by id.

	Returns:
		Tuple[object, ...]: Decoded move objects.
	"""
	return tuple(move_pool[move_id] for move_id in edge_move_ids)


def compact_ucs_structures(
	frontier,
	current_state_id,
	keep_size,
	best_cost,
	best_node_index,
	parent_index_arena,
	edge_move_ids_arena,
	state_id_arena,
	state_cache,
):
	"""Compact UCS arenas/maps to keep frontier-reachable history.

	Args:
		frontier: Priority queue of frontier nodes.
		current_state_id: Currently expanded state id.
		keep_size: Number of frontier nodes to keep.
		best_cost: Best known cost map.
		best_node_index: State id to arena index map.
		parent_index_arena: Parent index arena.
		edge_move_ids_arena: Edge move id arena.
		state_id_arena: Arena state id list.
		state_cache: Cached state objects.
	"""
	best_frontier_nodes = nsmallest(keep_size, frontier)
	keep_frontier_ids = {node[-1] for node in best_frontier_nodes}
	keep_frontier_ids.add(current_state_id)

	keep_node_indices = set()
	for state in keep_frontier_ids:
		node_idx = best_node_index.get(state)
		while node_idx is not None and node_idx >= 0 and node_idx not in keep_node_indices:
			keep_node_indices.add(node_idx)
			node_idx = parent_index_arena[node_idx]

	if len(keep_node_indices) >= len(best_node_index):
		return

	old_to_new_index = {}
	new_parent_index_arena = []
	new_edge_move_ids_arena = []
	new_state_id_arena = []

	for old_idx in sorted(keep_node_indices):
		old_parent_idx = parent_index_arena[old_idx]
		new_parent_idx = -1 if old_parent_idx < 0 else old_to_new_index[old_parent_idx]

		new_idx = len(new_parent_index_arena)
		old_to_new_index[old_idx] = new_idx

		new_parent_index_arena.append(new_parent_idx)
		new_edge_move_ids_arena.append(edge_move_ids_arena[old_idx])
		new_state_id_arena.append(state_id_arena[old_idx])

	new_best_node_index = {
		state: old_to_new_index[node_idx]
		for state, node_idx in best_node_index.items()
		if node_idx in old_to_new_index
	}
	new_state_cache = {
		state: state_cache[state]
		for state in keep_frontier_ids
		if state in state_cache
	}

	best_node_index.clear()
	best_node_index.update(new_best_node_index)

	parent_index_arena[:] = new_parent_index_arena
	edge_move_ids_arena[:] = new_edge_move_ids_arena
	state_id_arena[:] = new_state_id_arena

	state_cache.clear()
	state_cache.update(new_state_cache)
