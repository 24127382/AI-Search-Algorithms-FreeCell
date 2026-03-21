"""A* Search solver.

Uses UCS edge costs for g(n) and an admissible, consistent heuristic for h(n).

Key design decisions
--------------------
g(n)  — `ucs_move_cost` from ucs_utils, same as the UCS solver.  Foundation
         moves cost 1; tableau/freecell moves cost 10 adjusted for structural
         bonuses and penalties.  Minimum edge cost is always >= 1.

h(n)  — Any admissible, consistent heuristic from heuristics.py.  Defaults to
         `combined_heuristic` (max of foundation_distance and buried_cards).
         Both components are admissible w.r.t. UCS costs because every card
         still needs >= 1 foundation move at cost 1, so h never overestimates.

f(n)  — g(n) + h(n).  Heap priority.

Closed set — Because the heuristic is consistent (h(n) <= cost(n,n') + h(n')),
             the first time A* pops a node its g-cost is provably optimal.  We
             add it to a closed set and never re-expand it.  This is cheaper
             than UCS's stale-heap-pop guard and is the standard A* guarantee.

Tie-breaking — Within equal f, prefer lower h (i.e. closer to goal).  Within
               equal h, use the same `_priority_bias` as UCS (foundation
               progress, empty columns, free cells).  Within equal bias, use
               insertion order counter so the heap stays deterministic.

Path reconstruction — Identical arena/pool approach as UCS so paths are
                      returned as the same list-of-Move objects.
"""

from heapq import heappop, heappush
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


class AStarAlgorithm:
    """A* solver that reuses UCS edge costs for g(n).

    Attributes:
        game_state:     Initial board state.
        heuristic_func: Default heuristic used when search() receives None.
        last_run_stats: Statistics dict populated after each search() call.
    """

    def __init__(self, game_state, heuristic_func: Optional[Callable] = None):
        """Initialise A* with a start state and optional default heuristic.

        Args:
            game_state:     Initial board state.
            heuristic_func: Admissible heuristic callable h(state) -> int.
                            Defaults to combined_heuristic when omitted.
        """
        self.game_state = game_state
        self.heuristic_func = heuristic_func or combined_heuristic
        self.last_run_stats = None

    # ── Public interface ──────────────────────────────────────────────────────

    def search(self, heuristic_func: Optional[Callable] = None) -> Optional[List]:
        """Run A* and return the optimal move path.

        Args:
            heuristic_func: Override heuristic for this run.  Falls back to
                            the heuristic supplied at construction time.

        Returns:
            list[Move] | None: Optimal path from start to goal, or None when
                               the search space is exhausted without a solution.
        """
        h = heuristic_func or self.heuristic_func
        return self._search(h)

    # ── Tie-breaking ──────────────────────────────────────────────────────────

    @staticmethod
    def _priority_bias(state) -> int:
        """Secondary sort key for equal-f nodes.

        Mirrors UCS._priority_bias exactly so both solvers prefer the same
        "most-promising" state when costs are tied.

        A higher board-progress score maps to a lower bias value, meaning
        nodes with more cards on foundations and more free space sort earlier.

        Args:
            state: Candidate state.

        Returns:
            int: Bias value; smaller = higher priority.
        """
        foundation_bits = state.foundation_bits
        foundation_total = (
            (foundation_bits & 0xF)
            + ((foundation_bits >> 4) & 0xF)
            + ((foundation_bits >> 8) & 0xF)
            + ((foundation_bits >> 12) & 0xF)
        )
        empty_tableau = sum(1 for col in state.tableau if not col)
        occupied_freecells = sum(1 for card in state.freecells if card is not None)
        progress_score = (foundation_total * 16) + (empty_tableau * 3) - occupied_freecells
        return -progress_score

    # ── Path reconstruction ───────────────────────────────────────────────────

    @staticmethod
    def _reconstruct_path(
        node_index: int,
        parent_index_arena: list,
        edge_move_ids_arena: list,
        move_pool: list,
    ) -> list:
        """Walk parent links backward to recover the full move sequence.

        Identical logic to UCS._reconstruct_path so the two solvers always
        return paths in the same format.

        Args:
            node_index:          Index of the goal node in the arena.
            parent_index_arena:  Arena of parent node indices.
            edge_move_ids_arena: Arena of interned edge-move id tuples.
            move_pool:           Pool of interned Move objects.

        Returns:
            list[Move]: Moves from start to goal in forward order.
        """
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

    # ── Core search ───────────────────────────────────────────────────────────

    def _search(self, heuristic_func: Callable) -> Optional[List]:
        """Internal A* implementation.

        Heap tuple layout: (f, h, priority_bias, counter, state_id)

          f             — g + h; primary sort key.
          h             — heuristic value; tie-breaks equal-f nodes (lower h
                          preferred: already closer to goal).
          priority_bias — structural tie-breaker copied from UCS.
          counter       — insertion counter; keeps the heap deterministic and
                          avoids comparing State objects directly.
          state_id      — integer board identifier for O(1) lookup.

        The closed set is the authoritative "expanded" record.  Because the
        heuristic is consistent, the first pop of any state_id always carries
        the optimal g-cost, so we never need to re-expand.

        Args:
            heuristic_func: Admissible, consistent heuristic h(state) -> int.

        Returns:
            list[Move] | None: Optimal solution path, or None if unsolvable.
        """
        started_at = perf_counter()
        counter = 0

        start_state    = self.game_state
        start_state_id = state_id(start_state)
        h_start        = heuristic_func(start_state)
        f_start        = h_start  # g=0 at start

        # ── Frontier ─────────────────────────────────────────────────────────
        # Each entry: (f, h, priority_bias, counter, state_id)
        frontier: list = []
        heappush(
            frontier,
            (f_start, h_start, self._priority_bias(start_state), counter, start_state_id),
        )

        # ── Cost and closed-set tracking ─────────────────────────────────────
        # g_cost maps state_id -> best known path cost so far.
        # closed holds state_ids that have been expanded (g is now optimal).
        g_cost: dict = {start_state_id: 0}
        closed: set  = set()

        # ── Path-reconstruction arena (same layout as UCS) ───────────────────
        # Index 0 is the virtual root node for the start state.
        best_node_index:    dict = {start_state_id: 0}
        parent_index_arena: list = [-1]        # -1 = no parent (root)
        edge_move_ids_arena: list = [()]       # empty tuple = no incoming edge

        # Interned move storage (shared across all paths)
        move_pool:               list = []
        move_index_by_signature: dict = {}

        # Cached state objects keyed by state_id.
        # Evicted on expansion to bound memory; reconstructed on demand
        # (but A* never needs to revisit a closed state).
        state_cache: dict = {start_state_id: start_state}

        # ── Statistics ───────────────────────────────────────────────────────
        stats = {
            "expanded_nodes":     0,
            "generated_nodes":    0,
            "stale_heap_pops":    0,
            "pruned_by_cost":     0,
            "pruned_by_closed":   0,
            "peak_frontier_size": 1,
            "peak_closed_size":   0,
            "move_pool_size":     0,
        }

        # ── Main loop ────────────────────────────────────────────────────────
        while frontier:
            f, h_val, _, _, current_state_id = heappop(frontier)

            # ── Closed-set guard ─────────────────────────────────────────────
            # With a consistent heuristic, the first expansion is always
            # optimal.  Any later pop of the same state_id is stale.
            if current_state_id in closed:
                stats["stale_heap_pops"] += 1
                continue

            current_state = state_cache.pop(current_state_id, None)
            if current_state is None:
                # State was evicted before expansion (should not happen in
                # standard A*, but guard defensively).
                stats["stale_heap_pops"] += 1
                continue

            closed.add(current_state_id)
            current_node_index = best_node_index[current_state_id]
            current_g = g_cost[current_state_id]

            stats["expanded_nodes"] += 1
            if len(closed) > stats["peak_closed_size"]:
                stats["peak_closed_size"] = len(closed)

            # ── Goal check on expansion ──────────────────────────────────────
            # Checking on expansion (not generation) is correct for
            # non-uniform costs: guarantees the returned path is optimal.
            if current_state.is_goal:
                path = self._reconstruct_path(
                    current_node_index,
                    parent_index_arena,
                    edge_move_ids_arena,
                    move_pool,
                )
                stats["move_pool_size"]   = len(move_pool)
                stats["elapsed_seconds"]  = perf_counter() - started_at
                stats["solution_found"]   = True
                self.last_run_stats = stats
                return path

            # ── Move generation ──────────────────────────────────────────────
            # Pass last_move for immediate-undo pruning (same as UCS).
            incoming_edge_ids = edge_move_ids_arena[current_node_index]
            last_move = move_pool[incoming_edge_ids[-1]] if incoming_edge_ids else None
            candidate_moves = get_valid_moves(current_state, last_move=last_move)

            # ── Expand neighbours ────────────────────────────────────────────
            for move in candidate_moves:
                next_state, forced_moves = apply_move_with_forced(current_state, move)
                edge_moves    = (move, *forced_moves)
                next_state_id = state_id(next_state)

                # Skip already-expanded states (closed-set pruning).
                if next_state_id in closed:
                    stats["pruned_by_closed"] += 1
                    continue

                # ── g(next) = g(current) + edge cost ─────────────────────────
                # Edge cost mirrors UCS exactly:
                #   - ucs_move_cost for the user move (context-aware)
                #   - flat ucs_move_cost for each forced foundation move
                edge_cost = ucs_move_cost(
                    move, prev_state=current_state, next_state=next_state
                )
                if forced_moves:
                    edge_cost += sum(ucs_move_cost(fm) for fm in forced_moves)

                next_g = current_g + edge_cost
                stats["generated_nodes"] += 1

                # ── Cost pruning ─────────────────────────────────────────────
                # If we already know a cheaper or equal route to next_state,
                # this path cannot improve on it.
                old_g = g_cost.get(next_state_id)
                if old_g is not None and next_g >= old_g:
                    stats["pruned_by_cost"] += 1
                    continue

                # ── Compute f and update data structures ─────────────────────
                next_h = heuristic_func(next_state)
                next_f = next_g + next_h

                # Intern edge moves and record the new arena node.
                # If next_state_id already has a node from a more expensive
                # path, the new node replaces it via best_node_index.  The
                # old arena entry becomes unreachable (minor orphan overhead,
                # acceptable without compaction for A*).
                edge_move_ids = encode_edge_moves(
                    edge_moves, move_index_by_signature, move_pool
                )
                node_index = len(parent_index_arena)

                g_cost[next_state_id]          = next_g
                best_node_index[next_state_id] = node_index
                parent_index_arena.append(current_node_index)
                edge_move_ids_arena.append(edge_move_ids)
                state_cache[next_state_id] = next_state

                counter += 1
                heappush(
                    frontier,
                    (next_f, next_h, self._priority_bias(next_state), counter, next_state_id),
                )

                if len(frontier) > stats["peak_frontier_size"]:
                    stats["peak_frontier_size"] = len(frontier)

        # ── Exhausted without solution ────────────────────────────────────────
        stats["move_pool_size"]  = len(move_pool)
        stats["elapsed_seconds"] = perf_counter() - started_at
        stats["solution_found"]  = False
        self.last_run_stats = stats
        return None
