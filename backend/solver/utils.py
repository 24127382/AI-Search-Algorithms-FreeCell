import random
from backend.model.models import VALID_RANK, VALID_SUITS, Card

def _generate_zobrist_table():
    """Generates a Zobrist hashing table with 16 position-specific hashes per card.
    
    Positions 0-7: Tableau columns
    Positions 8-11: Freecells
    Positions 12-15: Foundations
    """
    table = {}
    for suit in VALID_SUITS:
        for rank in VALID_RANK:
            card = Card(suit=suit, rank=rank)
            # Each card gets 16 position-specific hash values
            table[card] = [random.getrandbits(64) for _ in range(16)]
    return table

ZOBRIST_TABLE = _generate_zobrist_table()