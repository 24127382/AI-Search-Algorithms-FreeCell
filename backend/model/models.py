'''
models.py

This module defines the data structures for the freecell game.

Usage:
    1. Create Card objects with suit and rank
    2. Use State to represent game snapshots
    3. State is immutable - create a new State for each move
'''
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


VALID_RANK = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
VALID_SUITS = ['hearts', 'diamonds', 'clubs', 'spades']
LOCATIONS = ['tableau', 'freecell', 'foundation']

# Frozen dataclass ensures Card objects are immutable and hashable
@dataclass(frozen=True, order=True)
class Card:
    """Playing card with suit and rank.
    
    Example:
        card = Card(suit='hearts', rank='A')
    """
    suit: str
    rank: str

    def __post_init__(self):
        """Validate and initialize. Sets color attribute on frozen instance."""
        if self.rank not in VALID_RANK:
            raise ValueError(f"Invalid rank: {self.rank}")
        if self.suit not in VALID_SUITS:
            raise ValueError(f"Invalid suit: {self.suit}")
        object.__setattr__(self, "color", 'red' if self.suit in ['hearts', 'diamonds'] else 'black')
        
        # Precompute values for speed
        rank_val = VALID_RANK.index(self.rank) + 1
        suit_idx = VALID_SUITS.index(self.suit)
        object.__setattr__(self, "_id", suit_idx * 13 + rank_val)
        object.__setattr__(self, "rank_val", rank_val)
        object.__setattr__(self, "suit_idx", suit_idx)

    def to_int(self) -> int:
        return self._id

@dataclass(frozen=True)
class State:
    """Game state snapshot: tableau, freecells, and foundations.
    
    Workflow - How to use State:
        1. Copy current state: new_tableau = [list(col) for col in current_state.tableau]
        2. Apply action: new_tableau[0].pop()  # Move a card
        3. Create new State: new_state = State(new_tableau, freecells, foundations)
        4. Use new_state for next iteration (old state remains unchanged)
    
    Why immutable? Enables hashing for visited set in search algorithms.
    """""
    tableau: Tuple[Tuple[Card, ...], ...]  # 8 columns of cards
    freecells: Tuple[Card, ...]  # 4 free cells for temporary storage
    foundations: Tuple[Tuple[Card, ...], ...]  # 4 foundation piles (one per suit)
    
    def __init__(self, tableau: List[List[Card]], freecells: List[Optional[Card]], foundations: List[List[Card]]):
        # Convert list to tuple to ensure immutability and hashability with each state is unique
        object.__setattr__(self, 'tableau', tuple(tuple(col) for col in tableau))
        object.__setattr__(self, 'freecells', tuple(freecells))
        object.__setattr__(self, 'foundations', tuple(tuple(f) for f in foundations))
                
        # 1. Encode Foundations (4 suits, rank 0-13 -> 4 bits each -> 16 bits)
        fnd_val = 0
        for f in self.foundations:
            fnd_val = (fnd_val << 4) | len(f)
            
        # 2. Encode Freecells (4 cells, sorted, 0-52 -> 6 bits each -> 24 bits)
        fc_ints = sorted(c.to_int() for c in self.freecells if c is not None)
        fc_val = 0
        for i in range(4):
            val = fc_ints[i] if i < len(fc_ints) else 0
            fc_val = (fc_val << 6) | val
            
        # 3. Encode Tableau (8 columns, sorted canonical, max ~19 cards per col)
        # Each column encoded as an integer, then sort those integers to canonicalize!
        col_ints = []
        for col in self.tableau:
            col_v = 0
            for c in col:
                col_v = (col_v << 6) | c.to_int()
            col_ints.append(col_v)
        col_ints.sort()
        
        # Combine columns into a single giant integer (using a fixed max 20 cards * 6 bits = 120 bits per col)
        # To make it simpler and perfectly safe, we'll just shift each by 120 bits
        tab_val = 0
        for col_v in col_ints:
            tab_val = (tab_val << 120) | col_v
            
        # Board Integer: Combine all
        board_int = (tab_val << 40) | (fc_val << 16) | fnd_val
        
        object.__setattr__(self, '_board_int', board_int)

    def __eq__(self, other):
        """Check if two states are equal using canonical int representation."""
        if not isinstance(other, State):
            return False
        return self._board_int == other._board_int
       
    def __hash__(self):
        """Hash for visited set in search algorithms."""
        return hash(self._board_int)

@dataclass(frozen=True)
class Move:
    '''Represents a move in the game.'''
    move_type: str  # 'tableau_to_tableau', 'tableau_to_freecell', etc.
    card: Card
    from_pos: Tuple[str, int]  # e.g., ('tableau', 0) or ('freecell', 1)
    to_pos: Tuple[str, int]  # e.g., ('tableau', 1) or ('foundation', 0)