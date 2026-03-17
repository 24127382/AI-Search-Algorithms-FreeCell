"""Uniform Cost Search solver."""

from heapq import heapify, heappop, heappush, nsmallest

from backend.engine.engine import apply_move_with_forced, get_valid_moves
from backend.solver.ucs.ucs_profile import (
    UCS_COMPACTION_GAP,
    UCS_FRONTIER_KEEP_SIZE,
    UCS_MAX_FRONTIER_SIZE,
    UCS_MAX_MOVES_PER_STATE,
    UCS_MAX_VISITED_STATES,
)
from backend.solver.ucs.ucs_utils import compact_ucs_maps, state_id, ucs_move_cost


class UCSAlgorithm:
    def __init__(self, game_state, mode="fast"):
        self.game_state = game_state
        if mode not in {"fast", "exact"}:
            raise ValueError(f"Unsupported UCS mode: {mode}")
        self.mode = mode

    def search(self):
        use_fast_mode = self.mode == "fast"
        counter = 0
        start_state = self.game_state
        start_state_id = state_id(start_state)
        frontier = []
        heappush(frontier, (0, counter, start_state_id, start_state))

        best_cost = {start_state_id: 0}
        transposition_best_g = {start_state_id: 0}
        parent = {start_state_id: None}
        move_from_parent = {start_state_id: None}
        last_move_from_parent = {start_state_id: None}
        next_compaction_at = UCS_MAX_VISITED_STATES

        while frontier:
            cost, _, current_state_id, current_state = heappop(frontier)

            if cost != best_cost.get(current_state_id):
                continue

            if current_state.is_goal:
                path = []
                node_id = current_state_id
                while parent[node_id] is not None:
                    edge_moves = move_from_parent[node_id] or ()
                    path.extend(reversed(edge_moves))
                    node_id = parent[node_id]
                path.reverse()
                return path

            if use_fast_mode and len(frontier) >= UCS_MAX_FRONTIER_SIZE:
                frontier = nsmallest(UCS_FRONTIER_KEEP_SIZE, frontier)
                heapify(frontier)

            if use_fast_mode and len(best_cost) >= next_compaction_at:
                compact_ucs_maps(frontier, current_state_id, best_cost, parent, move_from_parent)
                next_compaction_at = max(UCS_MAX_VISITED_STATES, len(best_cost) + UCS_COMPACTION_GAP)

            candidate_moves = get_valid_moves(current_state, last_move=last_move_from_parent.get(current_state_id))
            if use_fast_mode and len(candidate_moves) > UCS_MAX_MOVES_PER_STATE:
                candidate_moves.sort(key=ucs_move_cost)
                candidate_moves = candidate_moves[:UCS_MAX_MOVES_PER_STATE]

            for move in candidate_moves:
                next_state, forced_moves = apply_move_with_forced(current_state, move)
                edge_moves = (move, *forced_moves)
                next_state_id = state_id(next_state)
                edge_cost = sum(ucs_move_cost(applied_move) for applied_move in edge_moves)
                new_cost = cost + edge_cost

                best_known_g = transposition_best_g.get(next_state_id)
                if best_known_g is not None and new_cost >= best_known_g:
                    continue

                old_cost = best_cost.get(next_state_id)
                if old_cost is not None and new_cost >= old_cost:
                    continue

                transposition_best_g[next_state_id] = new_cost
                best_cost[next_state_id] = new_cost
                parent[next_state_id] = current_state_id
                move_from_parent[next_state_id] = edge_moves
                last_move_from_parent[next_state_id] = edge_moves[-1]
                counter += 1
                heappush(frontier, (new_cost, counter, next_state_id, next_state))

            if use_fast_mode and len(last_move_from_parent) > (UCS_MAX_VISITED_STATES * 2):
                last_move_from_parent = {
                    state: last_move_from_parent.get(state)
                    for state in best_cost
                }

        return None
