"""Weighted A* Search solver.

Cost model
----------
g(n)  — UCS edge costs via `ucs_move_cost`. Costs are environment-tunable
         through UCS_* variables and intentionally shared with UCS so both
         algorithms optimize the same move valuation model.

h(n)  — max(foundation_distance, buried_cards).  Admissible.

f(n)  — g(n) + weight * h(n).  The weight (default from ASTAR_WEIGHT)
         stays meaningful relative to UCS g-values which grow fast.

         Suboptimality bound: the returned solution cost is at most
         `weight` times the true optimal cost.  weight=5 is a good
         starting point; raise it if the search is still slow.

         This bound relies on the shared UCS edge-cost model remaining
         non-negative (enforced in `ucs_move_cost`).

Memory management
-----------------
No hard node-cap is applied. The search runs until it finds a solution,
is cancelled externally, or exhausts the frontier.

Closed/reopen policy
--------------------
Expanded states are tracked by best known closed g-cost.  If a better g is
found later, the state is reopened.  This protects result quality when the
heuristic is inconsistent while keeping stale-pop checks cheap.
"""

from heapq import heappop, heappush
from time import perf_counter
from typing import Callable, List, Optional

from backend.engine.engine import apply_move_with_forced, get_valid_moves
from backend.experiments.solver_stats import SolverStats
from backend.solver.search_utils.astar_utils import (
    finalize_astar_outcome,
    maybe_compact_astar_arena,
)
from backend.solver.search_utils.ucs_utils import (
    encode_edge_moves,
    reconstruct_interned_path,
    ucs_move_cost,
)
from backend.solver.utils.heuristics import combined_heuristic
from backend.solver.utils.utility import (
    astar_default_weight,
    env_zero_is_false,
    state_id,
    structural_priority_bias,
)

ASTAR_RUNTIME_LOG_ENABLED = env_zero_is_false("ASTAR_RUNTIME_LOG", default=True)
_ASTAR_COMPACT_MIN_ARENA_NODES = 4096
_ASTAR_COMPACT_ARENA_LIVE_RATIO = 2


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
        weight: Optional[float] = None,
        should_cancel: Optional[Callable] = None,
    ):
        self.game_state = game_state
        self.heuristic_func = heuristic_func or combined_heuristic
        self.weight = (
            astar_default_weight() if weight is None else max(0.0, float(weight))
        )
        self.should_cancel = should_cancel or (lambda: False)
        self.last_run_stats = None

    def search(self, heuristic_func: Optional[Callable] = None) -> Optional[List]:
        """Run weighted A* with the provided heuristic or the default one.

            Heap entry layout: (f, h, priority_bias, counter, g, state_id)
          f             — g + w*h.  Primary sort key.
          h             — raw heuristic value.  Tie-breaks equal-f entries;
                          lower h preferred (state is closer to goal).
          priority_bias — structural quality tie-breaker.
          counter       — insertion order; avoids comparing State objects.
          g             — path cost used to detect stale heap entries.
          state_id      — integer board id.

        Args:
            heuristic_func: Admissible h(state) -> int.

        Returns:
            list[Move] | None: Solution path or None.
        """
        heuristic_func = heuristic_func or self.heuristic_func
        w = self.weight
        started_at = perf_counter()
        counter = 0

        start = self.game_state
        start_id = state_id(start)
        h0 = heuristic_func(start)
        f0 = w * h0  # g=0 at start

        # ── Frontier ─────────────────────────────────────────────────────────
        # Tuple: (f, h, bias, counter, g, state_id)
        frontier: list = []
        heappush(
            frontier, (f0, h0, structural_priority_bias(start), counter, 0, start_id)
        )

        # ── g_cost: best known g for each discovered state ────────────────────
        g_cost: dict = {start_id: 0}

        # ── Closed map: expanded state -> best closed g ───────────────────────
        closed_best_g: dict = {}

        # ── Path-reconstruction arena ─────────────────────────────────────────
        # All three lists are parallel: index i describes the same node.
        best_node_index: dict = {start_id: 0}
        parent_index_arena: list = [-1]  # -1 = root, no parent
        edge_move_ids_arena: list = [()]  # empty = no incoming edge

        move_pool: list = []
        move_index_by_signature: dict = {}

        # State objects stored until expansion, evicted afterward.
        state_cache: dict = {start_id: start}

        # ── Statistics ────────────────────────────────────────────────────────
        stats = SolverStats.astar_defaults(w)

        # ── Main loop ─────────────────────────────────────────────────────────
        while frontier:
            if self.should_cancel():
                stats["stop_reason"] = "cancelled"
                stats["solution_length"] = 0
                self.last_run_stats = finalize_astar_outcome(
                    stats,
                    started_at,
                    solution_found=False,
                    move_pool_size=len(move_pool),
                    frontier_size=len(frontier),
                    closed_size=len(closed_best_g),
                    runtime_log_enabled=ASTAR_RUNTIME_LOG_ENABLED,
                )
                return None

            # ── Peak tracking ─────────────────────────────────────────────────
            if len(frontier) > stats["peak_frontier_size"]:
                stats["peak_frontier_size"] = len(frontier)
            if len(g_cost) > stats["peak_g_cost_size"]:
                stats["peak_g_cost_size"] = len(g_cost)

            # ── Pop best node ─────────────────────────────────────────────────
            _, _, _, _, popped_g, current_id = heappop(frontier)

            best_known_g = g_cost.get(current_id)
            if best_known_g is None or popped_g != best_known_g:
                stats["stale_heap_pops"] += 1
                continue

            # ── Closed-map stale guard ────────────────────────────────────────
            closed_g = closed_best_g.get(current_id)
            if closed_g is not None and popped_g > closed_g:
                stats["stale_heap_pops"] += 1
                continue

            current_state = state_cache.pop(current_id, None)
            if current_state is None:
                stats["stale_heap_pops"] += 1
                continue

            current_g = best_known_g
            current_node_index = best_node_index[current_id]
            closed_best_g[current_id] = current_g
            if len(closed_best_g) > stats["peak_closed_size"]:
                stats["peak_closed_size"] = len(closed_best_g)

            stats["expanded_nodes"] += 1

            # ── Goal check ────────────────────────────────────────────────────
            # Checked on expansion (not generation) to ensure the path we
            # reconstruct is the one with the best g we managed to find.
            if current_state.is_goal:
                path = reconstruct_interned_path(
                    current_node_index,
                    parent_index_arena,
                    edge_move_ids_arena,
                    move_pool,
                )
                stats["move_pool_size"] = len(move_pool)
                stats["stop_reason"] = "solved"
                stats["solution_cost"] = current_g
                stats["solution_length"] = len(path)
                self.last_run_stats = finalize_astar_outcome(
                    stats,
                    started_at,
                    solution_found=True,
                    move_pool_size=len(move_pool),
                    frontier_size=len(frontier),
                    closed_size=len(closed_best_g),
                    runtime_log_enabled=ASTAR_RUNTIME_LOG_ENABLED,
                )
                return path

            # ── Move generation ───────────────────────────────────────────────
            incoming_edge_ids = edge_move_ids_arena[current_node_index]
            last_move = move_pool[incoming_edge_ids[-1]] if incoming_edge_ids else None
            candidate_moves = get_valid_moves(
                current_state,
                last_move=last_move,
                prune_canonical_redundant=True,
            )

            # ── Expand neighbours ─────────────────────────────────────────────
            for move in candidate_moves:
                if self.should_cancel():
                    stats["stop_reason"] = "cancelled"
                    stats["solution_length"] = 0
                    self.last_run_stats = finalize_astar_outcome(
                        stats,
                        started_at,
                        solution_found=False,
                        move_pool_size=len(move_pool),
                        frontier_size=len(frontier),
                        closed_size=len(closed_best_g),
                        runtime_log_enabled=ASTAR_RUNTIME_LOG_ENABLED,
                    )
                    return None

                next_state, forced_moves = apply_move_with_forced(current_state, move)
                next_id = state_id(next_state)
                edge_moves = (move, *forced_moves)

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

                closed_next_g = closed_best_g.get(next_id)
                if closed_next_g is not None:
                    if next_g >= closed_next_g:
                        stats["pruned_by_closed"] += 1
                        continue
                    closed_best_g.pop(next_id, None)
                    stats["reopened_nodes"] += 1

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
                # is appended and the old one becomes an orphan.  Periodic
                # compaction reclaims unreachable arena nodes.
                edge_move_ids = encode_edge_moves(
                    edge_moves, move_index_by_signature, move_pool
                )
                node_index = len(parent_index_arena)

                g_cost[next_id] = next_g
                best_node_index[next_id] = node_index
                parent_index_arena.append(current_node_index)
                edge_move_ids_arena.append(edge_move_ids)
                state_cache[next_id] = next_state

                counter += 1
                heappush(
                    frontier,
                    (
                        next_f,
                        next_h,
                        structural_priority_bias(next_state),
                        counter,
                        next_g,
                        next_id,
                    ),
                )

                if (stats["generated_nodes"] % _ASTAR_COMPACT_MIN_ARENA_NODES) == 0:
                    maybe_compact_astar_arena(
                        parent_index_arena,
                        edge_move_ids_arena,
                        best_node_index,
                        stats,
                        compact_min_arena_nodes=_ASTAR_COMPACT_MIN_ARENA_NODES,
                        compact_live_ratio=_ASTAR_COMPACT_ARENA_LIVE_RATIO,
                    )

        # ── Frontier exhausted without solution ───────────────────────────────
        stats["stop_reason"] = "exhausted"
        stats["solution_length"] = 0
        self.last_run_stats = finalize_astar_outcome(
            stats,
            started_at,
            solution_found=False,
            move_pool_size=len(move_pool),
            frontier_size=len(frontier),
            closed_size=len(closed_best_g),
            runtime_log_enabled=ASTAR_RUNTIME_LOG_ENABLED,
        )
        return None
