"""Weighted A* Search solver.

Cost model
----------
g(n)  — UCS edge costs via `ucs_move_cost`.  Foundation moves cost 1;
         structural moves cost 7-16 depending on quality.  This is the same
         g as the UCS solver, preserving all domain knowledge about move value.

h(n)  — max(foundation_distance, buried_cards).  Always admissible.

f(n)  — g(n) + weight * h(n).  The weight (default 3.0) amplifies h so it
         stays meaningful relative to UCS g-values which grow fast.

         Suboptimality bound: the returned solution cost is at most
         `weight` times the true optimal cost.  weight=3 is a good
         starting point; raise it if the search is still slow.

Memory management
-----------------
Three mechanisms are combined, each borrowed directly from UCS:

1. Arena compaction (`compact_ucs_structures`): UCS costs are non-uniform so
   the same state can be re-discovered via a cheaper g, producing a new arena
   node while the old one becomes an orphan.  Compaction periodically walks
   the parent-link tree from every live frontier node and discards unreachable
   orphan entries, keeping arena size proportional to useful work done.

2. Frontier truncation: when the frontier exceeds MAX_FRONTIER, keep only the
   KEEP_FRONTIER best entries.  Ensures frontier memory is bounded even on
   hard deals where the search spreads wide before finding a solution.

3. Node cap: hard safety limit on total expansions.  Prevents OOM on the
   small fraction of pathological deals.

Closed set
----------
A closed set (not a stale-cost check) guards re-expansion.  Because the heap
stores f = g + w*h rather than g, we cannot cheaply compare a popped f
against g_cost without recomputing h.  The closed set is simpler: once a
state is expanded its path is accepted as good-enough (w-suboptimal) and
never revisited.  This is the standard weighted A* contract.
"""

import os
from heapq import heapify, heappop, heappush, nsmallest
from time import perf_counter
from typing import Callable, List, Optional

from backend.engine.engine import apply_move_with_forced, get_valid_moves
from backend.solver.heuristics import combined_heuristic
from backend.solver.ucs.ucs_utils import (
    decode_edge_moves,
    encode_edge_moves,
    state_id,
    ucs_move_cost,
)


ASTAR_RUNTIME_LOG_ENABLED = os.environ.get("ASTAR_RUNTIME_LOG", "1") != "0"

_LOG_INTERVAL = 2.0   # seconds between progress prints
_DEFAULT_MAX_NODES = int(os.environ.get("ASTAR_MAX_NODES", "1000000"))
_DEFAULT_MAX_FRONTIER = int(os.environ.get("ASTAR_MAX_FRONTIER", "250000"))
_DEFAULT_KEEP_FRONTIER = int(os.environ.get("ASTAR_KEEP_FRONTIER", "175000"))


def _make_profile(weight, max_nodes_override=None):
    """Derive A* runtime limits.

    Args:
        weight: Heuristic inflation factor.
        max_nodes_override: Optional hard cap on expanded nodes.

    Returns:
        dict: A* configuration profile.
    """
    max_frontier = max(1, _DEFAULT_MAX_FRONTIER)
    keep_frontier = max(1, min(_DEFAULT_KEEP_FRONTIER, max_frontier))
    return {
        "WEIGHT":                    weight,
        "MAX_NODES": max_nodes_override if max_nodes_override is not None
                     else _DEFAULT_MAX_NODES,
        "MAX_FRONTIER":              max_frontier,
        "KEEP_FRONTIER":             keep_frontier,
        "ENABLE_FRONTIER_TRUNCATION": True,
    }


class AStarAlgorithm:
    """Weighted A* solver with UCS edge costs and memory management.

    Attributes:
        game_state:     Initial board state.
        heuristic_func: h(state) -> int.  Should be admissible w.r.t. g=1
                        (any card needs at least 1 move to reach foundation).
                        Defaults to combined_heuristic = max(h2, h3).
        weight:         Heuristic inflation factor.  Higher = faster but more
                        suboptimal.  Typical range 2–5.
        last_run_stats: Statistics dict populated after each search() call.
    """

    def __init__(
        self,
        game_state,
        heuristic_func=None,
        weight: float = 5.0,
        max_nodes: Optional[int] = None,   # None = use machine-adaptive default,
        should_cancel: Optional[Callable] = None,
    ):
        self.game_state     = game_state
        self.heuristic_func = heuristic_func or combined_heuristic
        self.weight         = weight
        self.max_nodes      = max_nodes
        self.should_cancel = should_cancel or (lambda: False)
        self.last_run_stats = None

    def _finalize_stats(self, stats: dict, started_at: float, solution_found: bool) -> None:
        """Finalize and persist run statistics.

        Args:
            stats: Mutable stats dictionary.
            started_at: Run start timestamp from perf_counter().
            solution_found: Whether run found a valid solution path.
        """
        stats["elapsed_ms"] = (perf_counter() - started_at) * 1000
        stats["solution_found"] = solution_found
        expanded_nodes = max(stats.get("expanded_nodes", 0), 1)
        generated_nodes = stats.get("generated_nodes", 0)
        pruned_by_cost = stats.get("pruned_by_cost", 0)
        pruned_by_closed = stats.get("pruned_by_closed", 0)
        stats["effective_branching_factor"] = generated_nodes / expanded_nodes
        stats["cost_prune_rate"] = pruned_by_cost / max(generated_nodes, 1)
        stats["closed_prune_rate"] = pruned_by_closed / max(generated_nodes, 1)
        self.last_run_stats = stats

    def format_last_run_stats(self) -> str:
        """Build a compact human-readable report for last_run_stats.

        Returns:
            str: Multiline summary string.
        """
        if not self.last_run_stats:
            return "No A* stats available. Run search() first."

        stats = self.last_run_stats
        solution_cost = stats.get("solution_cost")
        solution_cost_text = "n/a" if solution_cost is None else str(solution_cost)

        lines = [
            "A* Run Stats",
            f"- solution_found: {stats.get('solution_found', False)}",
            f"- elapsed_ms: {stats.get('elapsed_ms', 0.0):.2f}",
            f"- solution_length: {stats.get('solution_length', 0)}",
            f"- solution_cost: {solution_cost_text}",
            f"- expanded_nodes: {stats.get('expanded_nodes', 0)}",
            f"- generated_nodes: {stats.get('generated_nodes', 0)}",
            f"- stale_heap_pops: {stats.get('stale_heap_pops', 0)}",
            f"- pruned_by_cost: {stats.get('pruned_by_cost', 0)}",
            f"- pruned_by_closed: {stats.get('pruned_by_closed', 0)}",
            f"- cost_prune_rate: {stats.get('cost_prune_rate', 0.0):.2%}",
            f"- closed_prune_rate: {stats.get('closed_prune_rate', 0.0):.2%}",
            f"- effective_branching_factor: {stats.get('effective_branching_factor', 0.0):.3f}",
            f"- peak_frontier_size: {stats.get('peak_frontier_size', 0)}",
            f"- peak_closed_size: {stats.get('peak_closed_size', 0)}",
            f"- final_frontier_size: {stats.get('final_frontier_size', 0)}",
            f"- final_closed_size: {stats.get('final_closed_size', 0)}",
            f"- move_pool_size: {stats.get('move_pool_size', 0)}",
        ]
        return "\n".join(lines)

    def _log_progress(self) -> None:
        """Print full runtime summary after an A* run ends."""
        print(self.format_last_run_stats())

    # ── Public interface ──────────────────────────────────────────────────────

    def search(self, heuristic_func: Optional[Callable] = None) -> Optional[List]:
        """Run weighted A* and return a solution path.

        Args:
            heuristic_func: Override heuristic for this run only.

        Returns:
            list[Move] | None: Solution path, or None if unsolved within cap.
        """

        profile = _make_profile(self.weight, self.max_nodes)
        return self._search(heuristic_func or self.heuristic_func, profile)

    # ── Tie-breaking ──────────────────────────────────────────────────────────

    @staticmethod
    def _priority_bias(state) -> int:
        """Structural tie-breaker for equal-f nodes.

        Mirrors UCS._priority_bias exactly.  Prefers states with more cards
        on foundations, more empty columns, and fewer occupied freecells.

        Returns:
            int: Lower value = higher priority.
        """
        bits = state.foundation_bits
        foundation_total = (
            (bits & 0xF)
            + ((bits >> 4) & 0xF)
            + ((bits >> 8) & 0xF)
            + ((bits >> 12) & 0xF)
        )
        empty_tableau      = sum(1 for col in state.tableau if not col)
        occupied_freecells = sum(1 for c in state.freecells if c is not None)
        score = (foundation_total * 16) + (empty_tableau * 3) - occupied_freecells
        return -score

    # ── Path reconstruction ───────────────────────────────────────────────────

    @staticmethod
    def _reconstruct_path(
        node_index: int,
        parent_index_arena: list,
        edge_move_ids_arena: list,
        move_pool: list,
    ) -> list:
        """Walk parent links backward to recover the full move sequence.

        Args:
            node_index:          Goal node index in the arena.
            parent_index_arena:  Per-node parent index.
            edge_move_ids_arena: Per-node interned edge-move id tuple.
            move_pool:           Interned Move objects.

        Returns:
            list[Move]: Forward-ordered move path from start to goal.
        """
        path = []
        walk = node_index
        while walk >= 0:
            edge_ids = edge_move_ids_arena[walk]
            if not edge_ids:
                break
            path.extend(reversed(decode_edge_moves(edge_ids, move_pool)))
            walk = parent_index_arena[walk]
        path.reverse()
        return path

    # ── Logging ───────────────────────────────────────────────────────────────

    def _log(self, started_at: float, stats: dict, frontier_size: int, g_cost_size: int) -> None:
        """Print a one-line progress snapshot.

        Args:
            started_at:    Run start timestamp.
            stats:         Current stats dict.
            frontier_size: Current frontier entry count.
            g_cost_size:   Current g_cost map size (unique states seen).
        """
        elapsed = perf_counter() - started_at
        print(
            f"[A*] w={self.weight}  "
            f"t={elapsed:.1f}s  "
            f"expanded={stats['expanded_nodes']}  "
            f"frontier={frontier_size}  "
            f"unique_seen={g_cost_size}  "
            f"pruned_closed={stats['pruned_by_closed']}  "
            f"pruned_cost={stats['pruned_by_cost']}"
        )

    # ── Core search ───────────────────────────────────────────────────────────

    def _search(self, heuristic_func: Callable, profile: dict) -> Optional[List]:
        """Internal weighted A* loop.

                Heap entry layout: (f, h, priority_bias, counter, g, state_id)
          f             — g + w*h.  Primary sort key.
          h             — raw heuristic value.  Tie-breaks equal-f entries;
                          lower h preferred (state is closer to goal).
          priority_bias — structural quality tie-breaker.
          counter       — insertion order; avoids comparing State objects.
                    g             — path cost used to detect stale heap entries.
          state_id      — integer board id. Last position required by
                                                    frontier truncation logic which uses node[-1].

        Args:
            heuristic_func: Admissible h(state) -> int.
            profile:        Runtime configuration dict from _make_profile.

        Returns:
            list[Move] | None: Solution path or None.
        """
        w          = profile["WEIGHT"]
        started_at = perf_counter()
        counter    = 0

        start    = self.game_state
        start_id = state_id(start)
        h0       = heuristic_func(start)
        f0       = w * h0   # g=0 at start

        # ── Frontier ─────────────────────────────────────────────────────────
        # Tuple: (f, h, bias, counter, g, state_id)
        # state_id is LAST so truncation can use node[-1].
        frontier: list = []
        heappush(frontier, (f0, h0, self._priority_bias(start), counter, 0, start_id))

        # ── g_cost: best known g for each discovered state ────────────────────
        g_cost: dict = {start_id: 0}

        # ── Closed set: expanded states, never re-expand ──────────────────────
        closed: set = set()

        # ── Path-reconstruction arena ─────────────────────────────────────────
        # All three lists are parallel: index i describes the same node.
        best_node_index:     dict = {start_id: 0}
        parent_index_arena:  list = [-1]        # -1 = root, no parent
        edge_move_ids_arena: list = [()]        # empty = no incoming edge
        state_id_arena:      list = [start_id]  # parallel to arena indices

        move_pool:               list = []
        move_index_by_signature: dict = {}

        # State objects stored until expansion, evicted afterward.
        state_cache: dict = {start_id: start}

        # ── Statistics ────────────────────────────────────────────────────────
        stats = {
            "weight":             w,
            "expanded_nodes":     0,
            "generated_nodes":    0,
            "stale_heap_pops":    0,
            "pruned_by_cost":     0,
            "pruned_by_closed":   0,
            "reopened_nodes":     0,
            "frontier_truncations": 0,
            "peak_frontier_size": 1,
            "peak_g_cost_size":   1,
            "peak_closed_size":   0,
            "move_pool_size":     0,
            "solution_cost":      None,
            "solution_length":    0,
            "node_cap_reached":   False,
        }

        next_log_at = started_at + _LOG_INTERVAL

        # ── Main loop ─────────────────────────────────────────────────────────
        while frontier:
            if self.should_cancel():
                return None


            now = perf_counter()

            # ── Periodic progress log ─────────────────────────────────────────
            if now >= next_log_at:
                self._log(started_at, stats, len(frontier), len(g_cost))
                next_log_at = now + _LOG_INTERVAL

            # ── Node cap ─────────────────────────────────────────────────────
            if stats["expanded_nodes"] >= profile["MAX_NODES"]:
                stats["node_cap_reached"]  = True
                stats["move_pool_size"]    = len(move_pool)
                stats["elapsed_seconds"]   = perf_counter() - started_at
                stats["solution_found"]    = False
                self.last_run_stats = stats
                print(
                    f"[A*] Node cap {profile['MAX_NODES']} reached.  "
                    f"frontier={len(frontier)}  unique_seen={len(g_cost)}"
                )
                return None

            # ── Frontier truncation ───────────────────────────────────────────
            # Caps frontier memory.  Drops weakest (highest-f) entries.
            # Mirrors UCS frontier truncation exactly, updated for 5-tuple.
            if (
                profile["ENABLE_FRONTIER_TRUNCATION"]
                and len(frontier) >= profile["MAX_FRONTIER"]
            ):
                frontier = nsmallest(profile["KEEP_FRONTIER"], frontier)
                heapify(frontier)
                keep_ids = {node[-1] for node in frontier}
                state_cache = {
                    sid: s for sid, s in state_cache.items() if sid in keep_ids
                }
                stats["frontier_truncations"] += 1

            # ── Peak tracking ─────────────────────────────────────────────────
            if len(frontier) > stats["peak_frontier_size"]:
                stats["peak_frontier_size"] = len(frontier)
            if len(g_cost) > stats["peak_g_cost_size"]:
                stats["peak_g_cost_size"] = len(g_cost)

            # ── Pop best node ─────────────────────────────────────────────────
            f, h_val, _, _, popped_g, current_id = heappop(frontier)

            best_known_g = g_cost.get(current_id)
            if best_known_g is None or popped_g != best_known_g:
                stats["stale_heap_pops"] += 1
                continue

            # ── Closed-set guard ──────────────────────────────────────────────
            if current_id in closed:
                stats["stale_heap_pops"] += 1
                continue

            current_state = state_cache.pop(current_id, None)
            if current_state is None:
                # Evicted by frontier truncation before expansion.
                stats["stale_heap_pops"] += 1
                continue

            closed.add(current_id)
            current_g          = best_known_g
            current_node_index = best_node_index[current_id]
            if len(closed) > stats["peak_closed_size"]:
                stats["peak_closed_size"] = len(closed)

            stats["expanded_nodes"] += 1

            # ── Goal check ────────────────────────────────────────────────────
            # Checked on expansion (not generation) to ensure the path we
            # reconstruct is the one with the best g we managed to find.
            if current_state.is_goal:
                path = self._reconstruct_path(
                    current_node_index,
                    parent_index_arena,
                    edge_move_ids_arena,
                    move_pool,
                )
                stats["move_pool_size"]   = len(move_pool)
                stats["solution_cost"] = current_g
                stats["solution_length"] = len(path)
                stats["final_frontier_size"] = len(frontier)
                stats["final_closed_size"] = len(closed)
                self._finalize_stats(stats, started_at, solution_found=True)
                if ASTAR_RUNTIME_LOG_ENABLED:
                    self._log_progress()
                return path

            # ── Move generation ───────────────────────────────────────────────
            incoming_edge_ids = edge_move_ids_arena[current_node_index]
            last_move = (
                move_pool[incoming_edge_ids[-1]] if incoming_edge_ids else None
            )
            candidate_moves = get_valid_moves(current_state, last_move=last_move)

            # ── Expand neighbours ─────────────────────────────────────────────
            for move in candidate_moves:
                if self.should_cancel():
                    return None

                next_state, forced_moves = apply_move_with_forced(current_state, move)
                next_id    = state_id(next_state)
                edge_moves = (move, *forced_moves)

                # Already optimally expanded under this weight.
                if next_id in closed:
                    stats["pruned_by_closed"] += 1
                    continue

                # ── Edge cost g(next) = g(current) + cost(move) ──────────────
                # Mirrors UCS edge cost exactly: ucs_move_cost for the user
                # move (context-aware), plus flat cost for each forced
                # foundation move that follows it.
                edge_cost = ucs_move_cost(
                    move, prev_state=current_state, next_state=next_state
                )
                if forced_moves:
                    edge_cost += sum(ucs_move_cost(fm) for fm in forced_moves)

                next_g = current_g + edge_cost
                stats["generated_nodes"] += 1

                # Prune if an equally-good-or-better path is already known.
                old_g = g_cost.get(next_id)
                if old_g is not None and next_g >= old_g:
                    stats["pruned_by_cost"] += 1
                    continue

                if next_id in closed:
                    closed.remove(next_id)
                    stats["reopened_nodes"] += 1

                # ── f = g + w * h ─────────────────────────────────────────────
                next_h = heuristic_func(next_state)
                next_f = next_g + w * next_h

                # Record the improved path.
                # If next_id was seen before with a worse g, a new arena node
                # is appended and the old one becomes an orphan.  Arena
                # compaction (above) will clean it up periodically.
                edge_move_ids = encode_edge_moves(
                    edge_moves, move_index_by_signature, move_pool
                )
                node_index = len(parent_index_arena)

                g_cost[next_id]          = next_g
                best_node_index[next_id] = node_index
                parent_index_arena.append(current_node_index)
                edge_move_ids_arena.append(edge_move_ids)
                state_id_arena.append(next_id)   # kept parallel for compaction
                state_cache[next_id] = next_state

                counter += 1
                heappush(
                    frontier,
                    (next_f, next_h, self._priority_bias(next_state), counter, next_g, next_id),
                )

        # ── Frontier exhausted without solution ───────────────────────────────
        stats["move_pool_size"] = len(move_pool)
        stats["final_frontier_size"] = len(frontier)
        stats["final_closed_size"] = len(closed)
        self._finalize_stats(stats, started_at, solution_found=False)
        if ASTAR_RUNTIME_LOG_ENABLED:
            self._log_progress()
        return None
