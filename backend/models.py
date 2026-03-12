'''
models.py

This module defines the data structures for the freecell game.

'''
class State:
    def __init__(self, tableau, freecells, foundations):
        pass
        
    def __eq__(self, other):
        """Check if two states are equal."""
        pass
       
    def __hash__(self):
        """Hash state for visited set storage."""
        pass
    
class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.color = None  # Placeholder for future implementation