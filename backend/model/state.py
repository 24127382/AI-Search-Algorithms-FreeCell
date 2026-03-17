"""State model for immutable FreeCell search snapshots."""

from dataclasses import dataclass, field
from typing import Iterable, Optional, Tuple

from backend.model.card import Card


@dataclass(frozen=True)
class State:
    """Immutable game state snapshot used by search algorithms."""

    tableau: Tuple[Tuple[Card, ...], ...]
    freecells: Tuple[Optional[Card], ...]
    foundations: Tuple[Tuple[Card, ...], ...]
    _encoded_columns: Tuple[Tuple[int, ...], ...] = field(init=False, repr=False, compare=False, hash=False)
    _foundation_bits: int = field(init=False, repr=False, compare=False, hash=False)
    _freecell_bits: int = field(init=False, repr=False, compare=False, hash=False)
    _top_signature: Tuple[int, ...] = field(init=False, repr=False, compare=False, hash=False)
    _board_key: Tuple[int, ...] = field(init=False, repr=False, compare=False, hash=False)
    _board_code: int = field(init=False, repr=False, compare=False, hash=False)
    _hash_value: int = field(init=False, repr=False, compare=False, hash=False)

    @property
    def is_goal(self) -> bool:
        """Check if all foundations are complete."""
        return all(foundation and foundation[-1].rank == "K" for foundation in self.foundations)

    def __post_init__(self):
        tableau = tuple(tuple(column) for column in self.tableau)
        freecells = tuple(self.freecells)
        foundations = tuple(tuple(stack) for stack in self.foundations)

        object.__setattr__(self, "tableau", tableau)
        object.__setattr__(self, "freecells", freecells)
        object.__setattr__(self, "foundations", foundations)
        self._refresh_cached_encodings()

    def _refresh_cached_encodings(self, encoded_columns: Optional[Tuple[Tuple[int, ...], ...]] = None):
        foundation_lengths = tuple(len(stack) for stack in self.foundations)
        packed_foundations = self._pack_foundation_lengths(foundation_lengths)
        packed_freecells = self._pack_freecells(self.freecells)

        if encoded_columns is None:
            encoded_columns = tuple(self._encode_column(column) for column in self.tableau)

        board_key = self._encode_board_key(foundation_lengths, encoded_columns)
        board_code = self._encode_board_integer(board_key)
        top_signature = self._build_top_signature(foundation_lengths)

        object.__setattr__(self, "_encoded_columns", encoded_columns)
        object.__setattr__(self, "_foundation_bits", packed_foundations)
        object.__setattr__(self, "_freecell_bits", packed_freecells)
        object.__setattr__(self, "_top_signature", top_signature)
        object.__setattr__(self, "_board_key", board_key)
        object.__setattr__(self, "_board_code", board_code)
        object.__setattr__(self, "_hash_value", hash(board_code))

    def _encode_column(self, column: Tuple[Card, ...]) -> Tuple[int, ...]:
        return tuple(card.to_int() for card in column)

    def _encode_board_key(
        self,
        foundation_key: Tuple[int, ...],
        encoded_columns: Tuple[Tuple[int, ...], ...],
    ) -> Tuple[int, ...]:
        freecell_cards = sorted(card.to_int() for card in self.freecells if card is not None)
        freecell_key = tuple(
            freecell_cards[idx] if idx < len(freecell_cards) else 0
            for idx in range(4)
        )
        tableau_key = tuple(sorted(encoded_columns))

        token_stream = [*foundation_key, *freecell_key]
        for column in tableau_key:
            token_stream.extend(column)
            token_stream.append(0)

        return tuple(token_stream)

    def _build_top_signature(self, foundation_lengths: Tuple[int, ...]) -> Tuple[int, ...]:
        tableau_top = tuple(column[-1].to_int() if column else 0 for column in self.tableau)
        freecell_sig = tuple(card.to_int() if card is not None else 0 for card in self.freecells)
        return (*tableau_top, *freecell_sig, *foundation_lengths)

    @staticmethod
    def _pack_foundation_lengths(foundation_lengths: Tuple[int, ...]) -> int:
        packed = 0
        for idx, length in enumerate(foundation_lengths):
            packed |= (length & 0xF) << (idx * 4)
        return packed

    @staticmethod
    def _pack_freecells(freecells: Tuple[Optional[Card], ...]) -> int:
        packed = 0
        for idx, card in enumerate(freecells):
            card_id = card.to_int() if card is not None else 0
            packed |= (card_id & 0x3F) << (idx * 6)
        return packed

    def _encode_board_integer(self, board_key: Tuple[int, ...]) -> int:
        board_code = 0
        for token in board_key:
            board_code = (board_code << 6) | (token + 1)
        return board_code

    def __eq__(self, other):
        if not isinstance(other, State):
            return False
        if self._board_code != other._board_code:
            return False
        return self._board_key == other._board_key

    def __hash__(self):
        return self._hash_value

    @property
    def board_code(self) -> int:
        return self._board_code

    @property
    def top_signature(self) -> Tuple[int, ...]:
        return self._top_signature

    @property
    def foundation_bits(self) -> int:
        return self._foundation_bits

    @property
    def freecell_bits(self) -> int:
        return self._freecell_bits

    @classmethod
    def from_transition(
        cls,
        prev_state: "State",
        tableau,
        freecells,
        foundations,
        touched_tableau_indices: Iterable[int],
    ) -> "State":
        normalized_tableau = tuple(tuple(col) for col in tableau)
        normalized_freecells = tuple(freecells)
        normalized_foundations = tuple(tuple(stack) for stack in foundations)

        encoded_columns = list(prev_state._encoded_columns)
        for idx in set(touched_tableau_indices):
            encoded_columns[idx] = tuple(card.to_int() for card in normalized_tableau[idx])

        state = cls.__new__(cls)
        object.__setattr__(state, "tableau", normalized_tableau)
        object.__setattr__(state, "freecells", normalized_freecells)
        object.__setattr__(state, "foundations", normalized_foundations)
        state._refresh_cached_encodings(encoded_columns=tuple(encoded_columns))
        return state

    @classmethod
    def from_lists(cls, tableau, freecells, foundations) -> "State":
        return cls(
            tableau=tuple(tuple(col) for col in tableau),
            freecells=tuple(freecells),
            foundations=tuple(tuple(s) for s in foundations),
        )
