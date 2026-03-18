"""Uniform Cost Search solver."""

from time import perf_counter
from heapq import heapify, heappop, heappush, nsmallest

from backend.engine.engine import apply_move_with_forced, get_valid_moves
from backend.solver.ucs.ucs_profile import (
    UCS_MODE_PROFILES,
    UCS_RUNTIME_LOG_ENABLED,
    UCS_RUNTIME_LOG_INTERVAL_SECONDS,
)
from backend.solver.ucs.ucs_utils import (
    BloomFilter,
    compact_ucs_structures,
    decode_edge_moves,
    encode_edge_moves,
    state_id,
    ucs_move_cost,
)


class UCSAlgorithm:
    """Uniform-Cost Search with configurable performance/memory trade-offs."""

    VALID_MODES = {"first", "speed", "memory"}

    def __init__(self, game_state, mode="speed"):
        """Initialize UCS with a fixed start state and execution mode."""
        self.game_state = game_state
        if mode not in self.VALID_MODES:
            raise ValueError(f"Unsupported UCS mode: {mode}")
        self.mode = mode
        self.last_run_stats = None

    def _mode_config(self):
        """Resolve runtime tuning knobs for the current mode."""
        return UCS_MODE_PROFILES[self.mode]

    def _finalize_stats(self, stats, started_at, solution_found):
        """Finalize run statistics and persist them on the solver instance."""
        stats["elapsed_seconds"] = perf_counter() - started_at
        stats["solution_found"] = solution_found
        self.last_run_stats = stats

    def _log_progress(self, started_at, stats, frontier_size, visited_size, window_expanded, window_seconds):
        """Emit periodic runtime telemetry for long UCS runs."""
        elapsed = max(perf_counter() - started_at, 1e-9)
        window_nodes_per_sec = window_expanded / max(window_seconds, 1e-9)
        print(
            "[UCS][Run] "
            f"mode={self.mode} "
            f"t={elapsed:.1f}s "
            f"frontier={frontier_size} "
            f"visited={visited_size} "
            f"expanded={stats['expanded_nodes']} "
            f"expanded/s={window_nodes_per_sec:.1f}"
        )

    @staticmethod
    def _priority_bias(state) -> int:
        """Tie-break equal-cost nodes by progress toward foundations."""
        foundation_bits = state.foundation_bits
        foundation_total = (
            (foundation_bits & 0xF)
            + ((foundation_bits >> 4) & 0xF)
            + ((foundation_bits >> 8) & 0xF)
            + ((foundation_bits >> 12) & 0xF)
        )
        empty_tableau = sum(1 for column in state.tableau if not column)
        occupied_freecells = sum(1 for card in state.freecells if card is not None)
        progress_score = (foundation_total * 16) + (empty_tableau * 3) - occupied_freecells
        return -progress_score

    @staticmethod
    def _reconstruct_path(node_index, parent_index_arena, edge_move_ids_arena, move_pool):
        """Rebuild the full move path by walking parent links backward."""
        path = []
        walk = node_index
        while walk >= 0:
            edge_move_ids = edge_move_ids_arena[walk]
            if not edge_move_ids:
                break
            edge_moves = decode_edge_moves(edge_move_ids, move_pool)
            path.extend(reversed(edge_moves))
            walk = parent_index_arena[walk]
        path.reverse()
        return path

    def _search_once(self, mode_config):
        """Run one UCS pass under a specific mode configuration."""
        started_at = perf_counter()
        counter = 0
        start_state = self.game_state
        start_state_id = state_id(start_state)

        frontier = []
        heappush(frontier, (0, self._priority_bias(start_state), counter, start_state_id))

        stats = {
            "mode": self.mode,
            "expanded_nodes": 0,
            "generated_nodes": 0,
            "stale_heap_pops": 0,
            "pruned_by_cost": 0,
            "peak_frontier_size": 1,
            "peak_visited_size": 1,
            "peak_state_cache_size": 1,
            "move_pool_size": 0,
            "pruned_by_bloom": 0,
            "partial_expansion_skipped": 0,
            "batch_pop_count": 0,
            "goal_candidates_found": 0,
        }

        best_cost = {start_state_id: 0}
        best_node_index = {start_state_id: 0}
        parent_index_arena = [-1]
        edge_move_ids_arena = [()]
        state_id_arena = [start_state_id]

        move_pool = []
        move_index_by_signature = {}
        bloom_filter = (
            BloomFilter(mode_config["BLOOM_BITS"], mode_config["BLOOM_HASH_COUNT"])
            if mode_config["ENABLE_BLOOM"]
            else None
        )
        if bloom_filter is not None:
            bloom_filter.add(start_state_id)

        state_cache = {start_state_id: start_state}
        next_compaction_at = mode_config["MAX_VISITED"]
        incumbent_goal_cost = None
        incumbent_path = None

        next_log_at = started_at + max(UCS_RUNTIME_LOG_INTERVAL_SECONDS, 0.1)
        last_log_time = started_at
        last_log_expanded = 0

        while frontier:
            if UCS_RUNTIME_LOG_ENABLED and perf_counter() >= next_log_at:
                now = perf_counter()
                window_seconds = now - last_log_time
                window_expanded = stats["expanded_nodes"] - last_log_expanded
                self._log_progress(started_at, stats, len(frontier), len(best_cost), window_expanded, window_seconds)
                last_log_time = now
                last_log_expanded = stats["expanded_nodes"]
                next_log_at = now + max(UCS_RUNTIME_LOG_INTERVAL_SECONDS, 0.1)

            if mode_config["USE_INCUMBENT_COST_BOUND"] and incumbent_goal_cost is not None and frontier[0][0] >= incumbent_goal_cost:
                stats["move_pool_size"] = len(move_pool)
                self._finalize_stats(stats, started_at, solution_found=incumbent_path is not None)
                if UCS_RUNTIME_LOG_ENABLED:
                    now = perf_counter()
                    window_seconds = now - last_log_time
                    window_expanded = stats["expanded_nodes"] - last_log_expanded
                    self._log_progress(started_at, stats, len(frontier), len(best_cost), window_expanded, window_seconds)
                return incumbent_path

            if mode_config["ENABLE_FRONTIER_TRUNCATION"] and len(frontier) >= mode_config["MAX_FRONTIER"]:
                frontier = nsmallest(mode_config["KEEP_FRONTIER"], frontier)
                heapify(frontier)
                keep_frontier_ids = {node_state_id for _, _, _, node_state_id in frontier}
                state_cache = {
                    node_state_id: state
                    for node_state_id, state in state_cache.items()
                    if node_state_id in keep_frontier_ids
                }

            if mode_config["ENABLE_ARENA_COMPACTION"] and len(best_cost) >= next_compaction_at and frontier:
                compact_ucs_structures(
                    frontier,
                    frontier[0][-1],
                    mode_config["KEEP_FRONTIER"],
                    best_cost,
                    best_node_index,
                    parent_index_arena,
                    edge_move_ids_arena,
                    state_id_arena,
                    state_cache,
                )
                next_compaction_at = max(mode_config["MAX_VISITED"], len(best_cost) + mode_config["COMPACTION_GAP"])

            if len(frontier) > stats["peak_frontier_size"]:
                stats["peak_frontier_size"] = len(frontier)
            if len(best_cost) > stats["peak_visited_size"]:
                stats["peak_visited_size"] = len(best_cost)
            if len(state_cache) > stats["peak_state_cache_size"]:
                stats["peak_state_cache_size"] = len(state_cache)

            pop_batch_size = mode_config["BATCH_EXPANSION_SIZE"]
            min_batch_cost = frontier[0][0]
            batch = []
            while frontier and len(batch) < pop_batch_size and frontier[0][0] == min_batch_cost:
                cost, _, _, current_state_id = heappop(frontier)

                best_known_cost = best_cost.get(current_state_id)
                if best_known_cost is None or cost != best_known_cost:
                    stats["stale_heap_pops"] += 1
                    continue

                current_node_index = best_node_index.get(current_state_id)
                if current_node_index is None:
                    stats["stale_heap_pops"] += 1
                    continue

                current_state = state_cache.pop(current_state_id, None)
                if current_state is None:
                    stats["stale_heap_pops"] += 1
                    continue

                batch.append((cost, current_state_id, current_node_index, current_state))

            if not batch:
                continue

            stats["batch_pop_count"] += 1

            for cost, _, current_node_index, current_state in batch:
                stats["expanded_nodes"] += 1

                if current_state.is_goal:
                    stats["goal_candidates_found"] += 1
                    path = self._reconstruct_path(current_node_index, parent_index_arena, edge_move_ids_arena, move_pool)

                    if mode_config["RETURN_FIRST_GOAL"]:
                        stats["move_pool_size"] = len(move_pool)
                        self._finalize_stats(stats, started_at, solution_found=True)
                        if UCS_RUNTIME_LOG_ENABLED:
                            now = perf_counter()
                            window_seconds = now - last_log_time
                            window_expanded = stats["expanded_nodes"] - last_log_expanded
                            self._log_progress(started_at, stats, len(frontier), len(best_cost), window_expanded, window_seconds)
                        return path

                    if incumbent_goal_cost is None or cost < incumbent_goal_cost:
                        incumbent_goal_cost = cost
                        incumbent_path = path
                    continue

                incoming_edge_move_ids = edge_move_ids_arena[current_node_index]
                last_move = move_pool[incoming_edge_move_ids[-1]] if incoming_edge_move_ids else None
                candidate_moves = get_valid_moves(current_state, last_move=last_move)

                move_cap = mode_config["MAX_MOVES_PER_STATE"]
                if move_cap > 0 and len(candidate_moves) > move_cap:
                    candidate_moves.sort(key=ucs_move_cost)
                    candidate_moves = candidate_moves[:move_cap]

                partial_width = mode_config["PARTIAL_EXPANSION_WIDTH"]
                if partial_width > 0 and len(candidate_moves) > partial_width:
                    stats["partial_expansion_skipped"] += len(candidate_moves) - partial_width
                    candidate_moves = candidate_moves[:partial_width]

                for move in candidate_moves:
                    next_state, forced_moves = apply_move_with_forced(current_state, move)
                    edge_moves = (move, *forced_moves)
                    next_state_id = state_id(next_state)
                    edge_cost = sum(ucs_move_cost(applied_move) for applied_move in edge_moves)
                    new_cost = cost + edge_cost
                    stats["generated_nodes"] += 1

                    if mode_config["EARLY_GOAL_BOUNDING"] and incumbent_goal_cost is not None and new_cost >= incumbent_goal_cost:
                        stats["pruned_by_cost"] += 1
                        continue

                    old_cost = best_cost.get(next_state_id)
                    if old_cost is not None and new_cost >= old_cost:
                        stats["pruned_by_cost"] += 1
                        continue

                    if bloom_filter is not None and old_cost is None and bloom_filter.maybe_contains(next_state_id):
                        stats["pruned_by_bloom"] += 1
                        continue

                    edge_move_ids = encode_edge_moves(edge_moves, move_index_by_signature, move_pool)
                    node_index = len(parent_index_arena)
                    best_cost[next_state_id] = new_cost
                    best_node_index[next_state_id] = node_index
                    parent_index_arena.append(current_node_index)
                    edge_move_ids_arena.append(edge_move_ids)
                    state_id_arena.append(next_state_id)
                    state_cache[next_state_id] = next_state
                    if bloom_filter is not None:
                        bloom_filter.add(next_state_id)
                    counter += 1
                    heappush(frontier, (new_cost, self._priority_bias(next_state), counter, next_state_id))

        stats["move_pool_size"] = len(move_pool)
        if incumbent_path is not None:
            self._finalize_stats(stats, started_at, solution_found=True)
            if UCS_RUNTIME_LOG_ENABLED:
                now = perf_counter()
                window_seconds = now - last_log_time
                window_expanded = stats["expanded_nodes"] - last_log_expanded
                self._log_progress(started_at, stats, len(frontier), len(best_cost), window_expanded, window_seconds)
            return incumbent_path

        self._finalize_stats(stats, started_at, solution_found=False)
        if UCS_RUNTIME_LOG_ENABLED:
            now = perf_counter()
            window_seconds = now - last_log_time
            window_expanded = stats["expanded_nodes"] - last_log_expanded
            self._log_progress(started_at, stats, len(frontier), len(best_cost), window_expanded, window_seconds)
        return None

    def search(self):
        """Run UCS and optionally fall back to safer modes when needed."""
        mode_config = self._mode_config()
        path = self._search_once(mode_config)
        if path is not None:
            return path

        for fallback_mode in mode_config.get("FALLBACK_MODES", ()): 
            fallback_solver = UCSAlgorithm(self.game_state, mode=fallback_mode)
            fallback_path = fallback_solver.search()
            if fallback_path is not None:
                self.last_run_stats = dict(fallback_solver.last_run_stats or {})
                self.last_run_stats["fallback_from"] = self.mode
                return fallback_path

        return None
