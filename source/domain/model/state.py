"""State model for immutable FreeCell search snapshots."""

from dataclasses import dataclass, field
from typing import Iterable, Optional, Tuple

from source.domain.model.card import Card


@dataclass(frozen=True)
class State:
    """Immutable game state snapshot used by search algorithms.

    Attributes:
        tableau: Eight tableau columns, each as tuple of cards.
        freecells: Four freecell slots.
        foundations: Four foundation stacks.
    """

    tableau: Tuple[Tuple[Card, ...], ...]
    freecells: Tuple[Optional[Card], ...]
    foundations: Tuple[Tuple[Card, ...], ...]
    _encoded_columns: Tuple[Tuple[int, ...], ...] = field(
        init=False, repr=False, compare=False, hash=False
    )
    _foundation_bits: int = field(init=False, repr=False, compare=False, hash=False)
    _freecell_bits: int = field(init=False, repr=False, compare=False, hash=False)
    _top_signature: Tuple[int, ...] = field(
        init=False, repr=False, compare=False, hash=False
    )
    _sorted_encoded_columns: Tuple[Tuple[int, ...], ...] = field(
        init=False, repr=False, compare=False, hash=False
    )
    _tableau_token_stream: Tuple[int, ...] = field(
        init=False, repr=False, compare=False, hash=False
    )
    _board_key: Tuple[int, ...] = field(
        init=False, repr=False, compare=False, hash=False
    )
    _board_code: int = field(init=False, repr=False, compare=False, hash=False)
    _is_goal_cached: bool = field(init=False, repr=False, compare=False, hash=False)
    _hash_value: int = field(init=False, repr=False, compare=False, hash=False)

    @property
    def is_goal(self) -> bool:
        """Check whether all foundations are complete.

        Returns:
            bool: `True` when each foundation ends at King.
        """
        return self._is_goal_cached

    def __post_init__(self):
        """Normalize containers and initialize cached encodings."""
        tableau = tuple(tuple(column) for column in self.tableau)
        freecells = tuple(self.freecells)
        foundations = tuple(tuple(stack) for stack in self.foundations)

        object.__setattr__(self, "tableau", tableau)
        object.__setattr__(self, "freecells", freecells)
        object.__setattr__(self, "foundations", foundations)
        self._refresh_cached_encodings()

    def _refresh_cached_encodings(
        self,
        encoded_columns: Optional[Tuple[Tuple[int, ...], ...]] = None,
        sorted_encoded_columns: Optional[Tuple[Tuple[int, ...], ...]] = None,
        tableau_token_stream: Optional[Tuple[int, ...]] = None,
    ):
        """Refresh canonical encodings used for hashing and equality.

        Args:
            encoded_columns: Optional precomputed encoded tableau columns.
        """
        foundation_lengths = tuple(len(stack) for stack in self.foundations)
        packed_foundations = self._pack_foundation_lengths(foundation_lengths)
        packed_freecells = self._pack_freecells(self.freecells)

        if encoded_columns is None:
            encoded_columns = tuple(
                self._encode_column(column) for column in self.tableau
            )

        if sorted_encoded_columns is None:
            sorted_encoded_columns = tuple(sorted(encoded_columns))

        if tableau_token_stream is None:
            tableau_tokens = []
            for column in sorted_encoded_columns:
                tableau_tokens.extend(column)
                tableau_tokens.append(0)
            tableau_token_stream = tuple(tableau_tokens)

        freecell_key = self._build_freecell_key(self.freecells)
        board_key = self._encode_board_key(
            foundation_lengths,
            freecell_key,
            tableau_token_stream,
        )
        board_code = self._encode_board_integer(board_key)
        top_signature = self._build_top_signature(foundation_lengths)

        object.__setattr__(self, "_encoded_columns", encoded_columns)
        object.__setattr__(self, "_foundation_bits", packed_foundations)
        object.__setattr__(self, "_freecell_bits", packed_freecells)
        object.__setattr__(self, "_top_signature", top_signature)
        object.__setattr__(self, "_sorted_encoded_columns", sorted_encoded_columns)
        object.__setattr__(self, "_tableau_token_stream", tableau_token_stream)
        object.__setattr__(self, "_board_key", board_key)
        object.__setattr__(self, "_board_code", board_code)
        object.__setattr__(self, "_is_goal_cached", packed_foundations == 0xDDDD)
        object.__setattr__(self, "_hash_value", hash(board_code))

    def _encode_column(self, column: Tuple[Card, ...]) -> Tuple[int, ...]:
        """Encode one tableau column into compact card ids.

        Args:
            column: Tableau column cards.

        Returns:
            Tuple[int, ...]: Encoded card ids.
        """
        return tuple(card.to_int() for card in column)

    @staticmethod
    def _build_freecell_key(freecells: Tuple[Optional[Card], ...]) -> Tuple[int, ...]:
        """Build canonical sorted freecell key with zero padding."""
        freecell_cards = [card.to_int() for card in freecells if card is not None]
        freecell_cards.sort()
        while len(freecell_cards) < 4:
            freecell_cards.append(0)
        return tuple(freecell_cards[:4])

    def _encode_board_key(
        self,
        foundation_key: Tuple[int, ...],
        freecell_key: Tuple[int, ...],
        tableau_token_stream: Tuple[int, ...],
    ) -> Tuple[int, ...]:
        """Build canonical board key independent of ordering artifacts.

        Args:
            foundation_key: Foundation progress tokens.
            freecell_key: Canonical freecell key.
            tableau_token_stream: Flattened canonical tableau token stream.

        Returns:
            Tuple[int, ...]: Canonical token stream key.
        """
        return (*foundation_key, *freecell_key, *tableau_token_stream)

    def _build_top_signature(
        self, foundation_lengths: Tuple[int, ...]
    ) -> Tuple[int, ...]:
        """Build compact signature from visible tops and foundation lengths.

        Args:
            foundation_lengths: Lengths of the four foundation stacks.

        Returns:
            Tuple[int, ...]: Top-card signature used by heuristics/caching.
        """
        tableau_top = tuple(
            column[-1].to_int() if column else 0 for column in self.tableau
        )
        freecell_sig = tuple(
            card.to_int() if card is not None else 0 for card in self.freecells
        )
        return (*tableau_top, *freecell_sig, *foundation_lengths)

    @staticmethod
    def _pack_foundation_lengths(foundation_lengths: Tuple[int, ...]) -> int:
        """Pack four foundation lengths into a compact integer.

        Args:
            foundation_lengths: Lengths of foundation stacks.

        Returns:
            int: Packed bit representation.
        """
        packed = 0
        for idx, length in enumerate(foundation_lengths):
            packed |= (length & 0xF) << (idx * 4)
        return packed

    @staticmethod
    def _pack_freecells(freecells: Tuple[Optional[Card], ...]) -> int:
        """Pack up to four freecell cards into a compact integer.

        Args:
            freecells: Freecell slots.

        Returns:
            int: Packed bit representation.
        """
        packed = 0
        for idx, card in enumerate(freecells):
            card_id = card.to_int() if card is not None else 0
            packed |= (card_id & 0x3F) << (idx * 6)
        return packed

    def _encode_board_integer(self, board_key: Tuple[int, ...]) -> int:
        """Encode board key token stream into one integer.

        Args:
            board_key: Canonical board key token stream.

        Returns:
            int: Encoded board integer.
        """
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
        """Create a transition state while reusing untouched encodings.

        Args:
            prev_state: Previous state with reusable caches.
            tableau: Next tableau structure.
            freecells: Next freecell structure.
            foundations: Next foundation structure.
            touched_tableau_indices: Tableau indices changed by transition.

        Returns:
            State: Newly constructed state with refreshed caches.
        """
        normalized_tableau = cls._normalize_tableau(tableau)
        normalized_freecells = (
            freecells if isinstance(freecells, tuple) else tuple(freecells)
        )
        normalized_foundations = cls._normalize_foundations(foundations)

        touched_indices = tuple(dict.fromkeys(touched_tableau_indices))

        encoded_columns = list(prev_state._encoded_columns)
        for idx in touched_indices:
            encoded_columns[idx] = tuple(
                card.to_int() for card in normalized_tableau[idx]
            )

        sorted_encoded_columns = None
        tableau_token_stream = None
        if not touched_indices:
            sorted_encoded_columns = prev_state._sorted_encoded_columns
            tableau_token_stream = prev_state._tableau_token_stream

        state = cls.__new__(cls)
        object.__setattr__(state, "tableau", normalized_tableau)
        object.__setattr__(state, "freecells", normalized_freecells)
        object.__setattr__(state, "foundations", normalized_foundations)
        state._refresh_cached_encodings(
            encoded_columns=tuple(encoded_columns),
            sorted_encoded_columns=sorted_encoded_columns,
            tableau_token_stream=tableau_token_stream,
        )
        return state

    @staticmethod
    def _normalize_tableau(tableau) -> Tuple[Tuple[Card, ...], ...]:
        if isinstance(tableau, tuple) and all(isinstance(col, tuple) for col in tableau):
            return tableau
        return tuple(tuple(col) for col in tableau)

    @staticmethod
    def _normalize_foundations(foundations) -> Tuple[Tuple[Card, ...], ...]:
        if isinstance(foundations, tuple) and all(
            isinstance(stack, tuple) for stack in foundations
        ):
            return foundations
        return tuple(tuple(stack) for stack in foundations)

    @classmethod
    def from_lists(cls, tableau, freecells, foundations) -> "State":
        """Build a state from list-like board structures.

        Args:
            tableau: Tableau as nested iterables.
            freecells: Freecell slots.
            foundations: Foundation stacks.

        Returns:
            State: Immutable normalized state.
        """
        return cls(
            tableau=tuple(tuple(col) for col in tableau),
            freecells=tuple(freecells),
            foundations=tuple(tuple(s) for s in foundations),
        )
