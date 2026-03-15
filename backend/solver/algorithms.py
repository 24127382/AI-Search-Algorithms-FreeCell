"""Search algorithms for FreeCell solver."""

from heapq import heapify, heappop, heappush, nsmallest

from backend.engine.engine import apply_move, get_valid_moves, is_goal
from backend.solver.ucs_profile import (
    UCS_COMPACTION_GAP,
    UCS_FRONTIER_KEEP_SIZE,
    UCS_MAX_FRONTIER_SIZE,
    UCS_MAX_MOVES_PER_STATE,
    UCS_MAX_VISITED_STATES,
)
from backend.solver.ucs_utils import compact_ucs_maps, state_id, ucs_move_cost

class SearchAlgorithm:
    def __init__(self, game_state):
        self.game_state = game_state

    def search(self, algorithm, heuristic_func=None):
        algorithm_handlers = {
            "BFS": self._bfs,
            "DFS": self._dfs,
            "UCS": self._ucs,
            "A*": lambda: self._a_star(heuristic_func),
        }
        handler = algorithm_handlers.get(algorithm)
        if handler is None:
            raise ValueError(f"Unknown algorithm: {algorithm}")
        return handler()

    def _bfs(self):
        pass

    def _dfs(self):
        pass

    def _ucs(self):
        """Uniform Cost Search with memory compaction safeguards."""
        counter = 0
        start_state = self.game_state
        start_state_id = self._state_id(start_state)
        frontier = []
        heappush(frontier, (0, counter, start_state_id, start_state))

        best_cost = {start_state_id: 0}
        parent = {start_state_id: None}
        move_from_parent = {start_state_id: None}
        next_compaction_at = UCS_MAX_VISITED_STATES

        while frontier:
            cost, _, current_state_id, current_state = heappop(frontier)

            if cost != best_cost.get(current_state_id):
                continue

            if is_goal(current_state):
                path = []
                node_id = current_state_id
                while parent[node_id] is not None:
                    path.append(move_from_parent[node_id])
                    node_id = parent[node_id]
                path.reverse()
                return path

            if len(frontier) >= UCS_MAX_FRONTIER_SIZE:
                frontier = nsmallest(UCS_FRONTIER_KEEP_SIZE, frontier)
                heapify(frontier)

            if len(best_cost) >= next_compaction_at:
                self._compact_ucs_maps(frontier, current_state_id, best_cost, parent, move_from_parent)
                next_compaction_at = max(UCS_MAX_VISITED_STATES, len(best_cost) + UCS_COMPACTION_GAP)

            candidate_moves = get_valid_moves(current_state)
            if len(candidate_moves) > UCS_MAX_MOVES_PER_STATE:
                candidate_moves.sort(key=self._ucs_move_cost)
                candidate_moves = candidate_moves[:UCS_MAX_MOVES_PER_STATE]

            for move in candidate_moves:
                next_state = apply_move(current_state, move)
                next_state_id = self._state_id(next_state)
                new_cost = cost + self._ucs_move_cost(move)

                old_cost = best_cost.get(next_state_id)
                if old_cost is not None and new_cost >= old_cost:
                    continue

                best_cost[next_state_id] = new_cost
                parent[next_state_id] = current_state_id
                move_from_parent[next_state_id] = move
                counter += 1
                heappush(frontier, (new_cost, counter, next_state_id, next_state))

        return None

    def _state_id(self, state):
        return state_id(state)

    def _ucs_move_cost(self, move):
        return ucs_move_cost(move)

    def _compact_ucs_maps(self, frontier, current_state_id, best_cost, parent, move_from_parent):
        compact_ucs_maps(frontier, current_state_id, best_cost, parent, move_from_parent)

    def _a_star(self, heuristic_func=None):
        pass