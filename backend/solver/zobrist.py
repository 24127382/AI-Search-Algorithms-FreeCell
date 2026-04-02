"""Zobrist hashing implementation for FreeCell game states.

Zobrist hashing is a technique to compute a hash key for a game state using
random 64-bit integers assigned to each piece-position pair. The state hash
is computed as the XOR of all occupied piece-positions.

Advantages:
- O(1) incremental hash updates (vs O(n) for bit-packing)
- Near-perfect collision resistance with 64-bit keys
- Simple incremental updates during search

References:
- Zobrist, A. L. (1970). "A new hashing method with application for game playing"
- Used extensively in chess engines for transposition tables
"""

import random
from dataclasses import dataclass
from typing import Tuple, Optional

from backend.model.card import Card, VALID_RANK, VALID_SUITS
from backend.model.state import State


# 52 cards × 12 positions (8 tableau + 4 freecells) = 624 entries
# Actual positions:
#   0-7: Tableau columns 0-7 (index positions within column encoded as rank/suit combo)
#   8-11: Freecells 0-3 (linear position)
#   12-15: Foundations suit 0-3 (encoded by suit)


class ZobristTranscoder:
    """Encodes (card, position) → zobrist table index.
    
    Encoding scheme:
    - Cards: 52 unique cards (4 suits × 13 ranks)
    - Positions split by location type:
      • Tableau: each column can hold 0-13 cards; we encode (column, depth)
      • Freecell: 4 slots
      • Foundation: 4 card-specific positions (Ace-King per suit)
    """

    @staticmethod
    def card_id(card: Card) -> int:
        """Map a card to a unique 0-51 ID.
        
        Args:
            card: Card object (suit, rank).
        
        Returns:
            int: Card ID in [0, 51].
        """
        suit_idx = VALID_SUITS.index(card.suit)
        rank_idx = VALID_RANK.index(card.rank)
        return suit_idx * 13 + rank_idx

    @staticmethod
    def tableau_position_id(column: int, depth: int) -> int:
        """Encode a tableau position as (column, depth).
        
        Args:
            column: Tableau column (0-7).
            depth: Depth within column (0-12).
        
        Returns:
            int: Unique position ID for zobrist table.
        """
        # Use 8 bits column, 4 bits depth: gives room for 0-13 depths
        return column * 16 + depth

    @staticmethod
    def freecell_position_id(slot: int) -> int:
        """Encode a freecell position.
        
        Args:
            slot: Freecell slot (0-3).
        
        Returns:
            int: Unique position ID for zobrist table.
        """
        # Offset: 8 columns × 16 depths = 128
        return 128 + slot

    @staticmethod
    def foundation_position_id(suit: str) -> int:
        """Encode a foundation position (by suit).
        
        Args:
            suit: Suit string ('hearts', 'diamonds', 'clubs', 'spades').
        
        Returns:
            int: Unique position ID for zobrist table.
        """
        # Offset: 128 tableau + 4 freecells = 132
        suit_idx = VALID_SUITS.index(suit)
        return 132 + suit_idx


@dataclass
class ZobristTable:
    """A Zobrist random number table indexed by (card, position) pairs.
    
    Attributes:
        table: Dictionary mapping (card_id, position_id) → random 64-bit int.
        rng: Random generator seeded for reproducibility.
    """
    table: dict
    rng: random.Random

    def __init__(self, seed: int = 42):
        """Initialize the Zobrist table with random 64-bit integers.
        
        Args:
            seed: Random seed for reproducibility.
        """
        self.rng = random.Random(seed)
        self.table = {}
        self._populate_table()

    def _populate_table(self):
        """Fill the table with random 64-bit integers.
        
        We populate entries for all possible (card, position) pairs that
        can occur in a FreeCell game. This is a superset; not all pairs
        are reachable, but it simplifies the implementation.
        """
        # 52 cards
        for card_id in range(52):
            # Tableau: 8 columns × 16 depth slots
            for column in range(8):
                for depth in range(16):
                    pos_id = ZobristTranscoder.tableau_position_id(column, depth)
                    self.table[(card_id, pos_id)] = self._random_64bit()
            
            # Freecells: 4 slots
            for slot in range(4):
                pos_id = ZobristTranscoder.freecell_position_id(slot)
                self.table[(card_id, pos_id)] = self._random_64bit()
            
            # Foundations: 4 suits
            for suit in VALID_SUITS:
                pos_id = ZobristTranscoder.foundation_position_id(suit)
                self.table[(card_id, pos_id)] = self._random_64bit()

    def _random_64bit(self) -> int:
        """Generate a random 64-bit integer.
        
        Returns:
            int: Random value in [0, 2^64 - 1].
        """
        return self.rng.getrandbits(64)

    def get(self, card_id: int, position_id: int) -> int:
        """Retrieve zobrist key for (card, position) pair.
        
        Args:
            card_id: Card ID (0-51).
            position_id: Position ID.
        
        Returns:
            int: Zobrist random value.
        """
        return self.table.get((card_id, position_id), 0)


class ZobristHash:
    """Incremental zobrist hash computation for a FreeCell state.
    
    This class computes a full zorrist hash once, then supports O(1)
    incremental updates as cards move.
    
    Attributes:
        zobrist_table: The shared zobrist random number table.
        hash_value: Current zobrist hash (XOR of all card-position pairs).
    """

    def __init__(self, zobrist_table: ZobristTable):
        """Initialize zobrist hash computer.
        
        Args:
            zobrist_table: Shared zobrist table.
        """
        self.zobrist_table = zobrist_table
        self.hash_value = 0

    def hash_state(self, state: State) -> int:
        """Compute complete zobrist hash for a state.
        
        Iterates through all cards in the state and XORs their
        zobrist values based on position.
        
        Args:
            state: FreeCell game state.
        
        Returns:
            int: Zobrist hash value.
        """
        self.hash_value = 0

        # Hash tableau
        for column_idx, column in enumerate(state.tableau):
            for depth, card in enumerate(column):
                card_id = ZobristTranscoder.card_id(card)
                pos_id = ZobristTranscoder.tableau_position_id(column_idx, depth)
                self.hash_value ^= self.zobrist_table.get(card_id, pos_id)

        # Hash freecells
        for slot, card in enumerate(state.freecells):
            if card is not None:
                card_id = ZobristTranscoder.card_id(card)
                pos_id = ZobristTranscoder.freecell_position_id(slot)
                self.hash_value ^= self.zobrist_table.get(card_id, pos_id)

        # Hash foundations
        for suit_idx, foundation in enumerate(state.foundations):
            suit = VALID_SUITS[suit_idx]
            for card in foundation:
                card_id = ZobristTranscoder.card_id(card)
                pos_id = ZobristTranscoder.foundation_position_id(suit)
                self.hash_value ^= self.zobrist_table.get(card_id, pos_id)

        return self.hash_value

    def update_move(
        self,
        card: Card,
        from_column: Optional[int],
        from_depth: Optional[int],
        from_freecell: Optional[int],
        from_foundation: Optional[int],
        to_column: Optional[int],
        to_depth: Optional[int],
        to_freecell: Optional[int],
        to_foundation: Optional[int],
    ) -> int:
        """Incrementally update hash after a card move.
        
        Moves a card from one (location, position) to another by XORing
        out the old position and XORing in the new position.
        
        Args:
            card: The card being moved.
            from_column, from_depth: Old tableau location (or None).
            from_freecell: Old freecell slot (or None).
            from_foundation: Old foundation suit (or None).
            to_column, to_depth: New tableau location (or None).
            to_freecell: New freecell slot (or None).
            to_foundation: New foundation suit (or None).
        
        Returns:
            int: Updated hash value.
        """
        card_id = ZobristTranscoder.card_id(card)

        # Remove old position
        if from_column is not None and from_depth is not None:
            pos_id = ZobristTranscoder.tableau_position_id(from_column, from_depth)
            self.hash_value ^= self.zobrist_table.get(card_id, pos_id)
        elif from_freecell is not None:
            pos_id = ZobristTranscoder.freecell_position_id(from_freecell)
            self.hash_value ^= self.zobrist_table.get(card_id, pos_id)
        elif from_foundation is not None:
            pos_id = ZobristTranscoder.foundation_position_id(from_foundation)
            self.hash_value ^= self.zobrist_table.get(card_id, pos_id)

        # Add new position
        if to_column is not None and to_depth is not None:
            pos_id = ZobristTranscoder.tableau_position_id(to_column, to_depth)
            self.hash_value ^= self.zobrist_table.get(card_id, pos_id)
        elif to_freecell is not None:
            pos_id = ZobristTranscoder.freecell_position_id(to_freecell)
            self.hash_value ^= self.zobrist_table.get(card_id, pos_id)
        elif to_foundation is not None:
            pos_id = ZobristTranscoder.foundation_position_id(to_foundation)
            self.hash_value ^= self.zobrist_table.get(card_id, pos_id)

        return self.hash_value

    def get_hash(self) -> int:
        """Get current hash value.
        
        Returns:
            int: Current zobrist hash.
        """
        return self.hash_value
