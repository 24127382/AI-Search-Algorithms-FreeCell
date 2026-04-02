"""Utility structures and helpers used by the UCS implementation."""

from typing import Dict, Iterable, List, Tuple

from backend.experiments.solver_stats import SolverStats
from backend.rule.rules import can_move_to_tableau
from backend.solver.utils.utility import env_int

_UCS_MEANINGLESS_FILL_MAX_SEQUENCE_LEN = env_int(
    "UCS_MEANINGLESS_FILL_MAX_SEQUENCE_LEN", 3, minimum=0
)
_UCS_MEANINGLESS_FILL_MIN_REMAINING_LEN = env_int(
    "UCS_MEANINGLESS_FILL_MIN_REMAINING_LEN", 1, minimum=0
)

_UCS_FOUNDATION_MOVE_COST = env_int("UCS_FOUNDATION_MOVE_COST", -5, minimum=-10000)
_UCS_BASE_MOVE_COST = env_int("UCS_BASE_MOVE_COST", 10, minimum=0)
_UCS_GOOD_TABLEAU_BUILD_BONUS = env_int("UCS_GOOD_TABLEAU_BUILD_BONUS", 3, minimum=0)
_UCS_CREATE_EMPTY_COLUMN_BONUS = env_int("UCS_CREATE_EMPTY_COLUMN_BONUS", 4, minimum=0)
_UCS_BREAK_STACK_PENALTY = env_int("UCS_BREAK_STACK_PENALTY", 6, minimum=0)
_UCS_MEANINGLESS_EMPTY_FILL_PENALTY = env_int(
    "UCS_MEANINGLESS_EMPTY_FILL_PENALTY", 6, minimum=0
)
_UCS_RESTRUCTURE_PENALTY_CAP = env_int("UCS_RESTRUCTURE_PENALTY_CAP", 18, minimum=1)
_UCS_TO_FREECELL_PENALTY = env_int("UCS_TO_FREECELL_PENALTY", 4, minimum=0)
_UCS_FROM_FREECELL_TO_TABLEAU_BONUS = env_int(
    "UCS_FROM_FREECELL_TO_TABLEAU_BONUS", 2, minimum=0
)
_UCS_FOUNDATION_PROGRESS_COST_CAP = env_int(
    "UCS_FOUNDATION_PROGRESS_COST_CAP", 1, minimum=-10000
)
_UCS_MIN_EDGE_COST = env_int("UCS_MIN_EDGE_COST", 1, minimum=-10000)


def _moved_sequence_len(move) -> int:
    """Return moved sequence length for a move."""
    return len(move.sequence) if move.sequence else 1


def is_good_tableau_build(move, prev_state=None) -> bool:
    """Check whether a tableau move strengthens tableau structure.

    A move is considered structurally good when it extends an existing column
    (top stack non-empty) with a legal alternating-color descending link.
    """
    if prev_state is None:
        return False
    if move.to_pos[0] != "tableau":
        return False

    dest_column = prev_state.tableau[move.to_pos[1]]
    if not dest_column:
        return False

    dest_top = dest_column[-1]
    return can_move_to_tableau(move.card, (dest_top,))


def is_breaking_stack(move, prev_state=None) -> bool:
    """Check whether move breaks an already well-built source stack."""
    if prev_state is None:
        return False
    if move.from_pos[0] != "tableau":
        return False

    source_column = prev_state.tableau[move.from_pos[1]]
    moved_len = _moved_sequence_len(move)
    remaining_len = len(source_column) - moved_len
    if remaining_len <= 0:
        return False

    moved_base = source_column[remaining_len]
    below_card = source_column[remaining_len - 1]
    return can_move_to_tableau(moved_base, (below_card,))


def is_creating_empty_column(move, prev_state=None) -> bool:
    """Check whether move frees an entire tableau column."""
    if prev_state is None:
        return False
    if move.from_pos[0] != "tableau":
        return False

    source_column = prev_state.tableau[move.from_pos[1]]
    return len(source_column) == _moved_sequence_len(move)


def is_filling_empty_column(move, prev_state=None) -> bool:
    """Check whether move goes into an empty tableau column."""
    if prev_state is None:
        return False
    if move.to_pos[0] != "tableau":
        return False

    return len(prev_state.tableau[move.to_pos[1]]) == 0


def is_meaningless_empty_column_fill(move, prev_state=None) -> bool:
    """Detect expensive empty-column fill patterns with low strategic value."""
    if not is_filling_empty_column(move, prev_state):
        return False

    sequence_len = _moved_sequence_len(move)
    if move.from_pos[0] == "tableau":
        source_column = prev_state.tableau[move.from_pos[1]]
        remaining_len = len(source_column) - sequence_len
        return (
            sequence_len <= _UCS_MEANINGLESS_FILL_MAX_SEQUENCE_LEN
            and remaining_len >= _UCS_MEANINGLESS_FILL_MIN_REMAINING_LEN
        )

    return False


def ucs_move_cost(move, prev_state=None, next_state=None):
    """Compute UCS edge cost for one move.

    Args:
            move: Move object.
            prev_state: Source state before applying the move.
            next_state: Destination state after applying the move.

    Returns:
            int: Edge cost used by UCS.
    """
    if move.to_pos[0] == "foundation":
        return max(_UCS_FOUNDATION_MOVE_COST, _UCS_MIN_EDGE_COST)

    cost = _UCS_BASE_MOVE_COST
    good_tableau_build = is_good_tableau_build(move, prev_state)
    creates_empty_column = is_creating_empty_column(move, prev_state)
    breaks_stack = is_breaking_stack(move, prev_state)
    meaningless_empty_fill = is_meaningless_empty_column_fill(move, prev_state)

    if good_tableau_build:
        cost -= _UCS_GOOD_TABLEAU_BUILD_BONUS

    if creates_empty_column:
        cost -= _UCS_CREATE_EMPTY_COLUMN_BONUS

    if breaks_stack:
        cost += _UCS_BREAK_STACK_PENALTY

    if meaningless_empty_fill:
        cost += _UCS_MEANINGLESS_EMPTY_FILL_PENALTY

    # Intentional trade-off: a move may improve destination structure while
    # still being discouraged when it breaks a well-ordered source stack.
    # Cap the compounded restructure penalty to avoid extreme spikes.
    if breaks_stack and meaningless_empty_fill:
        cost = min(cost, _UCS_RESTRUCTURE_PENALTY_CAP)

    if move.to_pos[0] == "freecell":
        cost += _UCS_TO_FREECELL_PENALTY

    if move.from_pos[0] == "freecell" and move.to_pos[0] == "tableau":
        cost -= _UCS_FROM_FREECELL_TO_TABLEAU_BONUS

    if next_state is not None:
        prev_foundation_total = (
            sum(len(stack) for stack in prev_state.foundations)
            if prev_state is not None
            else 0
        )
        next_foundation_total = sum(len(stack) for stack in next_state.foundations)
        if next_foundation_total > prev_foundation_total:
            cost = min(cost, _UCS_FOUNDATION_PROGRESS_COST_CAP)

    return max(int(cost), _UCS_MIN_EDGE_COST)


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


def intern_move(
    move,
    move_index_by_signature: Dict[
        Tuple[str, int, str, int, str, int, Tuple[int, ...]], int
    ],
    move_pool: List[object],
) -> int:
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


def encode_edge_moves(
    edge_moves: Iterable[object],
    move_index_by_signature: Dict[
        Tuple[str, int, str, int, str, int, Tuple[int, ...]], int
    ],
    move_pool: List[object],
) -> Tuple[int, ...]:
    """Convert edge move objects into interned id tuple.

    Args:
            edge_moves: Iterable of edge move objects.
            move_index_by_signature: Signature-to-id mapping.
            move_pool: Move pool indexed by id.

    Returns:
            Tuple[int, ...]: Interned edge move ids.
    """
    return tuple(
        intern_move(move, move_index_by_signature, move_pool) for move in edge_moves
    )


def decode_edge_moves(
    edge_move_ids: Tuple[int, ...], move_pool: List[object]
) -> Tuple[object, ...]:
    """Decode interned edge ids back into move objects.

    Args:
            edge_move_ids: Tuple of interned move ids.
            move_pool: Move pool indexed by id.

    Returns:
            Tuple[object, ...]: Decoded move objects.
    """
    return tuple(move_pool[move_id] for move_id in edge_move_ids)


def reconstruct_interned_path(
    node_index: int,
    parent_index_arena: List[int],
    edge_move_ids_arena: List[Tuple[int, ...]],
    move_pool: List[object],
) -> List[object]:
    """Reconstruct full move path from parent links and interned edge ids."""
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


def finalize_ucs_outcome(
    stats: dict,
    started_at: float,
    solution_found: bool,
    move_pool_size: int,
    frontier_size: int,
    visited_size: int,
    runtime_log_enabled: bool,
):
    """Finalize and optionally print UCS runtime stats."""
    stats["move_pool_size"] = move_pool_size
    stats["final_frontier_size"] = frontier_size
    stats["final_visited_size"] = visited_size
    finalized_stats = SolverStats.finalize_ucs(
        stats, started_at, solution_found=solution_found
    )
    if runtime_log_enabled:
        print(SolverStats.format_ucs(finalized_stats))
    return finalized_stats
