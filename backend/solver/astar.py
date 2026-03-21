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

from heapq import heapify, heappop, heappush, nsmallest
from time import perf_counter
from typing import Callable, List, Optional

from backend.engine.engine import apply_move_with_forced, get_valid_moves
from backend.solver.heuristics import combined_heuristic
from backend.solver.ucs.ucs_profile import UCS_MODE_PROFILES
from backend.solver.ucs.ucs_utils import (
    compact_ucs_structures,
    decode_edge_moves,
    encode_edge_moves,
    state_id,
    ucs_move_cost,
)

_LOG_INTERVAL = 2.0   # seconds between progress prints


def _make_profile(weight, max_nodes_override=None):
    """Derive A* runtime limits from UCS speed-mode machine limits.

    Reuses the machine-adaptive detection from ucs_profile so A* automatically
    scales to the host's RAM and CPU count.

    Args:
        weight: Heuristic inflation factor.

    Returns:
        dict: A* configuration profile.
    """
    s = UCS_MODE_PROFILES["speed"]
    return {
        "WEIGHT":                    weight,
        "MAX_NODES": max_nodes_override if max_nodes_override is not None
                     else s["MAX_VISITED"],
        "MAX_FRONTIER":              s["MAX_FRONTIER"],
        "KEEP_FRONTIER":             s["KEEP_FRONTIER"],
        "COMPACTION_GAP":            s["COMPACTION_GAP"],
        "ENABLE_FRONTIER_TRUNCATION": True,
        "ENABLE_ARENA_COMPACTION":    True,
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
        max_nodes: Optional[int] = None,   # None = use machine-adaptive default
    ):
        self.weight    = weight
        self.max_nodes = max_nodes          # stored, passed to _make_profile
        """Initialise the solver.

        Args:
            game_state:     Initial board state.
            heuristic_func: Admissible heuristic. Defaults to combined_heuristic.
            weight:         w in f = g + w*h.  Default 3.0.
        """
        self.game_state     = game_state
        self.heuristic_func = heuristic_func or combined_heuristic
        self.weight         = weight
        self.last_run_stats = None

    # ── Public interface ──────────────────────────────────────────────────────

    def search(self, heuristic_func: Optional[Callable] = None) -> Optional[List]:
        """Run weighted A* and return a solution path.

        Args:
            heuristic_func: Override heuristic for this run only.

        Returns:
            list[Move] | None: Solution path, or None if unsolved within cap.
        """

        """Adjust the second argument to increase expanded node cap"""
        profile = _make_profile(self.weight, 1000000)
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

        Heap entry layout: (f, h, priority_bias, counter, state_id)
          f             — g + w*h.  Primary sort key.
          h             — raw heuristic value.  Tie-breaks equal-f entries;
                          lower h preferred (state is closer to goal).
          priority_bias — structural quality tie-breaker.
          counter       — insertion order; avoids comparing State objects.
          state_id      — integer board id. Last position required by
                          compact_ucs_structures which uses node[-1].

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
        # Tuple: (f, h, bias, counter, state_id)
        # state_id is LAST so compact_ucs_structures can use node[-1].
        frontier: list = []
        heappush(frontier, (f0, h0, self._priority_bias(start), counter, start_id))

        # ── g_cost: best known g for each discovered state ────────────────────
        g_cost: dict = {start_id: 0}

        # ── Closed set: expanded states, never re-expand ──────────────────────
        closed: set = set()

        # ── Path-reconstruction arena ─────────────────────────────────────────
        # All three lists are parallel: index i describes the same node.
        # state_id_arena is needed by compact_ucs_structures to rebuild
        # best_node_index after compaction.
        best_node_index:     dict = {start_id: 0}
        parent_index_arena:  list = [-1]        # -1 = root, no parent
        edge_move_ids_arena: list = [()]        # empty = no incoming edge
        state_id_arena:      list = [start_id]  # parallel to arena indices

        move_pool:               list = []
        move_index_by_signature: dict = {}

        # State objects stored until expansion, evicted afterward.
        state_cache: dict = {start_id: start}

        # Compaction threshold: trigger when g_cost grows past this.
        next_compaction_at = profile["MAX_NODES"]

        # ── Statistics ────────────────────────────────────────────────────────
        stats = {
            "weight":             w,
            "expanded_nodes":     0,
            "generated_nodes":    0,
            "stale_heap_pops":    0,
            "pruned_by_cost":     0,
            "pruned_by_closed":   0,
            "arena_compactions":  0,
            "frontier_truncations": 0,
            "peak_frontier_size": 1,
            "peak_g_cost_size":   1,
            "move_pool_size":     0,
            "node_cap_reached":   False,
        }

        next_log_at = started_at + _LOG_INTERVAL

        # ── Main loop ─────────────────────────────────────────────────────────
        while frontier:

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

            # ── Arena compaction ──────────────────────────────────────────────
            # Cleans orphan arena entries created when a state is re-discovered
            # via a cheaper g-path (UCS costs are non-uniform so this happens).
            # compact_ucs_structures walks parent links from all frontier nodes
            # and discards unreachable entries, bounding arena size.
            if (
                profile["ENABLE_ARENA_COMPACTION"]
                and len(g_cost) >= next_compaction_at
                and frontier
            ):
                compact_ucs_structures(
                    frontier,
                    frontier[0][-1],         # next state_id to expand
                    profile["KEEP_FRONTIER"],
                    g_cost,                  # compact_ucs_structures calls this best_cost
                    best_node_index,
                    parent_index_arena,
                    edge_move_ids_arena,
                    state_id_arena,
                    state_cache,
                )
                next_compaction_at = max(
                    profile["MAX_NODES"],
                    len(g_cost) + profile["COMPACTION_GAP"],
                )
                stats["arena_compactions"] += 1

            # ── Peak tracking ─────────────────────────────────────────────────
            if len(frontier) > stats["peak_frontier_size"]:
                stats["peak_frontier_size"] = len(frontier)
            if len(g_cost) > stats["peak_g_cost_size"]:
                stats["peak_g_cost_size"] = len(g_cost)

            # ── Pop best node ─────────────────────────────────────────────────
            f, h_val, _, _, current_id = heappop(frontier)

            # ── Closed-set guard ──────────────────────────────────────────────
            # Handles stale frontier entries from:
            #   (a) states updated with cheaper g (orphan push),
            #   (b) states evicted by frontier truncation.
            if current_id in closed:
                stats["stale_heap_pops"] += 1
                continue

            current_state = state_cache.pop(current_id, None)
            if current_state is None:
                # Evicted by frontier truncation before expansion.
                stats["stale_heap_pops"] += 1
                continue

            closed.add(current_id)
            current_g          = g_cost[current_id]
            current_node_index = best_node_index[current_id]

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
                stats["move_pool_size"]  = len(move_pool)
                stats["elapsed_seconds"] = perf_counter() - started_at
                stats["solution_found"]  = True
                self.last_run_stats = stats
                print(
                    f"[A*] Solved: {len(path)} moves  "
                    f"expanded={stats['expanded_nodes']}  "
                    f"t={stats['elapsed_seconds']:.2f}s  "
                    f"w={w}"
                )
                return path

            # ── Move generation ───────────────────────────────────────────────
            incoming_edge_ids = edge_move_ids_arena[current_node_index]
            last_move = (
                move_pool[incoming_edge_ids[-1]] if incoming_edge_ids else None
            )
            candidate_moves = get_valid_moves(current_state, last_move=last_move)

            # ── Expand neighbours ─────────────────────────────────────────────
            for move in candidate_moves:
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
                    (next_f, next_h, self._priority_bias(next_state), counter, next_id),
                )

        # ── Frontier exhausted without solution ───────────────────────────────
        stats["move_pool_size"]  = len(move_pool)
        stats["elapsed_seconds"] = perf_counter() - started_at
        stats["solution_found"]  = False
        self.last_run_stats = stats
        return None
