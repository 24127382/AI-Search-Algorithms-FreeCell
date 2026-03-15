from heapq import nsmallest

from backend.solver.ucs_profile import UCS_VISITED_KEEP_SIZE


def state_id(state):
	board_int = getattr(state, "_board_int", None)
	if board_int is not None:
		return board_int
	return hash(state)


def ucs_move_cost(move):
	if move.to_pos[0] == "foundation":
		return 1
	if move.from_pos[0] == "freecell" and move.to_pos[0] == "tableau":
		return 2
	if move.from_pos[0] == "tableau" and move.to_pos[0] == "tableau":
		return 3
	if move.to_pos[0] == "freecell":
		return 4
	return 3


def compact_ucs_maps(frontier, current_state_id, best_cost, parent, move_from_parent):
	best_frontier_nodes = nsmallest(UCS_VISITED_KEEP_SIZE, frontier)
	keep_frontier_ids = {node_state_id for _, _, node_state_id, _ in best_frontier_nodes}
	keep_frontier_ids.add(current_state_id)

	keep_ids = set()
	for state in keep_frontier_ids:
		walk_id = state
		while walk_id is not None and walk_id not in keep_ids:
			keep_ids.add(walk_id)
			walk_id = parent.get(walk_id)

	if len(keep_ids) >= len(best_cost):
		return

	new_best_cost = {state: best_cost[state] for state in keep_ids if state in best_cost}
	new_parent = {state: parent.get(state) for state in keep_ids}
	new_move_from_parent = {state: move_from_parent.get(state) for state in keep_ids}

	best_cost.clear()
	best_cost.update(new_best_cost)
	parent.clear()
	parent.update(new_parent)
	move_from_parent.clear()
	move_from_parent.update(new_move_from_parent)
