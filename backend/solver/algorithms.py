'''
algorithms.py

This module implements search algorithms for freecell.

Algorithms included:
- BFS
- DFS
- UCS
- A*
'''
import os
from heapq import heappush, heappop, heapify, nsmallest
from backend.engine.engine import get_valid_moves, apply_move, is_goal

def _machine_fast_profile() -> dict:
    cpu_count = os.cpu_count() or 4
    if cpu_count >= 12:
        return {
            "MAX_VISITED": 120000,
            "MAX_FRONTIER": 160000,
            "KEEP_FRONTIER": 70000,
            "KEEP_VISITED": 60000,
            "COMPACTION_GAP": 30000,
            "MAX_MOVES_PER_STATE": 14,
        }
    if cpu_count >= 8:
        return {
            "MAX_VISITED": 100000,
            "MAX_FRONTIER": 130000,
            "KEEP_FRONTIER": 55000,
            "KEEP_VISITED": 48000,
            "COMPACTION_GAP": 25000,
            "MAX_MOVES_PER_STATE": 12,
        }
    return {
        "MAX_VISITED": 80000,
        "MAX_FRONTIER": 100000,
        "KEEP_FRONTIER": 42000,
        "KEEP_VISITED": 36000,
        "COMPACTION_GAP": 20000,
        "MAX_MOVES_PER_STATE": 10,
    }


UCS_PROFILE = _machine_fast_profile()
UCS_MAX_VISITED_STATES = UCS_PROFILE["MAX_VISITED"]
UCS_MAX_FRONTIER_SIZE = UCS_PROFILE["MAX_FRONTIER"]
UCS_FRONTIER_KEEP_SIZE = UCS_PROFILE["KEEP_FRONTIER"]
UCS_VISITED_KEEP_SIZE = UCS_PROFILE["KEEP_VISITED"]
UCS_COMPACTION_GAP = UCS_PROFILE["COMPACTION_GAP"]
UCS_MAX_MOVES_PER_STATE = UCS_PROFILE["MAX_MOVES_PER_STATE"]

class SearchAlgorithm:
    def __init__(self, game_state):
        self.game_state = game_state

    def search(self, algorithm, heuristic_func=None):
        if algorithm == 'BFS':
            return self._bfs()
        elif algorithm == 'DFS':
            return self._dfs()
        elif algorithm == 'UCS':
            return self._ucs()
        elif algorithm == 'A*':
            return self._a_star(heuristic_func)
        else:
            raise ValueError("Unknown algorithm: {}".format(algorithm))
        
    def _bfs(self):
        pass
    
    def _dfs(self):
        pass
    
    def _ucs(self):
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
        board_int = getattr(state, "_board_int", None)
        if board_int is not None:
            return board_int
        return hash(state)

    def _ucs_move_cost(self, move):
        if move.to_pos[0] == 'foundation':
            return 1
        if move.from_pos[0] == 'freecell' and move.to_pos[0] == 'tableau':
            return 2
        if move.from_pos[0] == 'tableau' and move.to_pos[0] == 'tableau':
            return 3
        if move.to_pos[0] == 'freecell':
            return 4
        return 3

    def _compact_ucs_maps(self, frontier, current_state_id, best_cost, parent, move_from_parent):
        best_frontier_nodes = nsmallest(UCS_VISITED_KEEP_SIZE, frontier)
        keep_frontier_ids = {state_id for _, _, state_id, _ in best_frontier_nodes}
        keep_frontier_ids.add(current_state_id)

        keep_ids = set()
        for state_id in keep_frontier_ids:
            walk_id = state_id
            while walk_id is not None and walk_id not in keep_ids:
                keep_ids.add(walk_id)
                walk_id = parent.get(walk_id)

        if len(keep_ids) >= len(best_cost):
            return

        new_best_cost = {state_id: best_cost[state_id] for state_id in keep_ids if state_id in best_cost}
        new_parent = {state_id: parent.get(state_id) for state_id in keep_ids}
        new_move_from_parent = {state_id: move_from_parent.get(state_id) for state_id in keep_ids}

        best_cost.clear()
        best_cost.update(new_best_cost)
        parent.clear()
        parent.update(new_parent)
        move_from_parent.clear()
        move_from_parent.update(new_move_from_parent)
    
    def _a_star(self):
        pass