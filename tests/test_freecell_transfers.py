from backend.engine.engine import get_valid_moves
from backend.model.card import Card
from backend.model.move import MoveType
from backend.model.state import State


def test_generates_freecell_to_freecell_when_target_empty():
    state = State.from_lists(
        tableau=[[] for _ in range(8)],
        freecells=[Card("hearts", "7"), None, None, None],
        foundations=[[], [], [], []],
    )

    valid_moves = get_valid_moves(state, prune_safe=False)

    assert any(
        move.move_type == MoveType.FREECELL_TO_FREECELL
        and move.from_pos == ("freecell", 0)
        and move.to_pos == ("freecell", 1)
        for move in valid_moves
    )


def test_does_not_generate_freecell_to_occupied_freecell():
    state = State.from_lists(
        tableau=[[] for _ in range(8)],
        freecells=[Card("hearts", "7"), Card("spades", "K"), None, None],
        foundations=[[], [], [], []],
    )

    valid_moves = get_valid_moves(state, prune_safe=False)

    assert not any(
        move.from_pos == ("freecell", 0) and move.to_pos == ("freecell", 1)
        for move in valid_moves
    )
