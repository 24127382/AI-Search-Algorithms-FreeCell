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

# Frozen dataclass ensures Card objects are immutable and hashable
@dataclass(frozen=True)
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

    def __eq__(self, other):
        """Check if two states are equal."""
        if not isinstance(other, State):
            return False
        return (self.tableau == other.tableau and 
                self.freecells == other.freecells and 
                self.foundations == other.foundations)
       
    def __hash__(self):
        """Hash for visited set in search algorithms."""
        return hash((self.tableau, self.freecells, self.foundations))

