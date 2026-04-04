"""Zobrist hashing utilities for FreeCell game states.

Zobrist hashing provides O(1) incremental hash updates via XOR operations,
making it ideal for search algorithms that explore large game trees.

The hash value for a state is the XOR of all (card, position) zobrist keys.
Moving a card requires just two XOR operations: remove old position, add new.

References:
- Zobrist, A. L. (1970). "A new hashing method with application for game playing"
- Used extensively in computer chess engines for transposition tables
"""

import random
from typing import Optional, Tuple

from source.domain.model.card import VALID_RANK, VALID_SUITS, Card
from source.domain.model.state import State


class ZobristTranscoder:
    """Encodes (card, position) pairs to zobrist table indices.

    Mapping scheme:
    - Cards: 52 unique IDs (4 suits × 13 ranks)
    - Positions:
      • Tableau: (column, depth) → column * 16 + depth (0-127)
      • Freecells: slot → 128 + slot (128-131)
      • Foundations: suit → 132 + suit_idx (132-135)
    """

    @staticmethod
    def card_id(card: Card) -> int:
        """Map card to unique 0-51 ID.

        Args:
            card: Card object.

        Returns:
            int: Card ID in [0, 51].
        """
        suit_idx = VALID_SUITS.index(card.suit)
        rank_idx = VALID_RANK.index(card.rank)
        return suit_idx * 13 + rank_idx

    @staticmethod
    def tableau_position_id(column: int, depth: int) -> int:
        """Encode tableau (column, depth) position.

        Args:
            column: Tableau column (0-7).
            depth: Depth within column (0-13).

        Returns:
            int: Unique position ID.
        """
        return column * 16 + depth

    @staticmethod
    def freecell_position_id(slot: int) -> int:
        """Encode freecell slot position.

        Args:
            slot: Freecell slot (0-3).

        Returns:
            int: Unique position ID (128-131).
        """
        return 128 + slot

    @staticmethod
    def foundation_position_id(suit: str | int) -> int:
        """Encode foundation position by suit.

        Args:
            suit: Suit string ('hearts', 'diamonds', 'clubs', 'spades')
                or suit index in range 0..3.

        Returns:
            int: Unique position ID (132-135).
        """
        if isinstance(suit, int):
            if suit < 0 or suit >= len(VALID_SUITS):
                raise ValueError(f"Invalid foundation suit index: {suit}")
            suit_idx = suit
        else:
            suit_idx = VALID_SUITS.index(suit)
        return 132 + suit_idx


class ZobristTable:
    """Zobrist random number table indexed by (card_id, position_id).

    Stores 64-bit random integers for all possible (card, position) pairs.
    Thread-safe single instance created at module load time.

    Attributes:
        table: Dict mapping (card_id, position_id) → 64-bit random int.
        rng: Seeded RNG for reproducibility.
    """

    def __init__(self, seed: int = 42):
        """Initialize zobrist table with seeded random values.

        Args:
            seed: Random seed for reproducibility. Default 42 for consistency.
        """
        self.rng = random.Random(seed)
        self.table = {}
        self._populate_table()

    def _populate_table(self):
        """Populate table with random 64-bit integers.

        Generates entries for:
        - All 52 cards × 8 tableau columns × 16 depth slots
        - All 52 cards × 4 freecell slots
        - All 52 cards × 4 foundation stacks

        Total: ~5156 entries (includes unreachable pairs for simplicity).
        """
        # 52 cards × (8*16 tableau + 4 freecells + 4 foundations)
        for card_id in range(52):
            # Tableau: 8 columns × 16 depths
            for column in range(8):
                for depth in range(16):
                    pos_id = ZobristTranscoder.tableau_position_id(column, depth)
                    self.table[(card_id, pos_id)] = self.rng.getrandbits(64)

            # Freecells: 4 slots
            for slot in range(4):
                pos_id = ZobristTranscoder.freecell_position_id(slot)
                self.table[(card_id, pos_id)] = self.rng.getrandbits(64)

            # Foundations: 4 suits
            for suit in VALID_SUITS:
                pos_id = ZobristTranscoder.foundation_position_id(suit)
                self.table[(card_id, pos_id)] = self.rng.getrandbits(64)

    def get(self, card_id: int, position_id: int) -> int:
        """Retrieve zobrist value for (card, position) pair.

        Args:
            card_id: Card ID (0-51).
            position_id: Position ID.

        Returns:
            int: 64-bit zobrist value (0 if not found).
        """
        return self.table.get((card_id, position_id), 0)


class ZobristHash:
    """Incremental zobrist hash for FreeCell states.

    Maintains a current hash value that can be updated O(1) per card move
    via XOR operations, supporting efficient state space exploration.

    Attributes:
        table: Reference to shared ZobristTable.
        hash_value: Current XOR hash of all (card, position) pairs.
    """

    def __init__(self, zobrist_table: ZobristTable):
        """Initialize zobrist hash computer.

        Args:
            zobrist_table: Shared zobrist table.
        """
        self.table = zobrist_table
        self.hash_value = 0

    def hash_state(self, state: State) -> int:
        """Compute full zobrist hash for a state.

        O(n) operation that iterates all cards and XORs their zobrist values.
        Used to initialize the hash on first state or reset if needed.

        Args:
            state: FreeCell game state.

        Returns:
            int: Zobrist hash value for the state.
        """
        self.hash_value = 0

        # Hash tableau
        for col_idx, column in enumerate(state.tableau):
            for depth, card in enumerate(column):
                card_id = ZobristTranscoder.card_id(card)
                pos_id = ZobristTranscoder.tableau_position_id(col_idx, depth)
                self.hash_value ^= self.table.get(card_id, pos_id)

        # Hash freecells
        for slot, card in enumerate(state.freecells):
            if card is not None:
                card_id = ZobristTranscoder.card_id(card)
                pos_id = ZobristTranscoder.freecell_position_id(slot)
                self.hash_value ^= self.table.get(card_id, pos_id)

        # Hash foundations
        for suit_idx, foundation in enumerate(state.foundations):
            suit = VALID_SUITS[suit_idx]
            for card in foundation:
                card_id = ZobristTranscoder.card_id(card)
                pos_id = ZobristTranscoder.foundation_position_id(suit)
                self.hash_value ^= self.table.get(card_id, pos_id)

        return self.hash_value

    def update_move(
        self,
        card: Card,
        from_column: Optional[int] = None,
        from_depth: Optional[int] = None,
        from_freecell: Optional[int] = None,
        from_foundation: Optional[str | int] = None,
        to_column: Optional[int] = None,
        to_depth: Optional[int] = None,
        to_freecell: Optional[int] = None,
        to_foundation: Optional[str | int] = None,
    ) -> int:
        """Incrementally update hash for a card move operation.

        O(1) operation: XOR out old position, XOR in new position.
        This maintains hash correctness while avoiding full recomputation.

        Args:
            card: The card being moved.
            from_column, from_depth: Old tableau location (or None).
            from_freecell: Old freecell slot (or None).
            from_foundation: Old foundation suit name or index (or None).
            to_column, to_depth: New tableau location (or None).
            to_freecell: New freecell slot (or None).
            to_foundation: New foundation suit name or index (or None).

        Returns:
            int: Updated hash value.
        """
        card_id = ZobristTranscoder.card_id(card)

        # Remove old position (XOR out)
        if from_column is not None and from_depth is not None:
            pos_id = ZobristTranscoder.tableau_position_id(from_column, from_depth)
            self.hash_value ^= self.table.get(card_id, pos_id)
        elif from_freecell is not None:
            pos_id = ZobristTranscoder.freecell_position_id(from_freecell)
            self.hash_value ^= self.table.get(card_id, pos_id)
        elif from_foundation is not None:
            pos_id = ZobristTranscoder.foundation_position_id(from_foundation)
            self.hash_value ^= self.table.get(card_id, pos_id)

        # Add new position (XOR in)
        if to_column is not None and to_depth is not None:
            pos_id = ZobristTranscoder.tableau_position_id(to_column, to_depth)
            self.hash_value ^= self.table.get(card_id, pos_id)
        elif to_freecell is not None:
            pos_id = ZobristTranscoder.freecell_position_id(to_freecell)
            self.hash_value ^= self.table.get(card_id, pos_id)
        elif to_foundation is not None:
            pos_id = ZobristTranscoder.foundation_position_id(to_foundation)
            self.hash_value ^= self.table.get(card_id, pos_id)

        return self.hash_value

    def get_hash(self) -> int:
        """Get current hash value.

        Returns:
            int: Current zobrist hash.
        """
        return self.hash_value


# Global zobrist table instance, initialized once at module load
_ZOBRIST_TABLE = ZobristTable(seed=42)


def get_zobrist_table() -> ZobristTable:
    """Get the global zobrist table.

    Returns:
        ZobristTable: Shared zobrist random number table.
    """
    return _ZOBRIST_TABLE


def zobrist_hash_state(state: State) -> int:
    """Compute zobrist hash for a state.

    Convenience function for one-off O(n) hash computations.
    For incremental hashing, create a ZobristHash instance instead.

    Args:
        state: FreeCell game state.

    Returns:
        int: Zobrist hash value.
    """
    hasher = ZobristHash(_ZOBRIST_TABLE)
    return hasher.hash_state(state)
