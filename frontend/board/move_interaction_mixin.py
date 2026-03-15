from backend.engine.engine import get_valid_moves
from backend.model.models import Card
from backend.rule.rules import get_movable_sequences
from frontend.board.constants import SLOT_FOUNDATION, SLOT_FREECELL, SLOT_TABLEAU
from frontend.card import SUIT_SYMBOL


class BoardMoveInteractionMixin:
	def _on_slot_source_clicked(self, source: tuple[str, int]):
		source_type, source_idx = source
		if source_type == SLOT_TABLEAU:
			self._on_tableau_target_clicked(source_idx)
		elif source_type == SLOT_FREECELL:
			self._on_freecell_clicked(source_idx)

	def _on_tableau_card_clicked(self, pos: tuple):
		if self.state is None:
			return

		col_idx = pos[1]
		if not self.state.tableau[col_idx]:
			return

		if self.selected_source is None:
			selection = self._resolve_tableau_selection(col_idx, pos)
			if selection is None:
				return

			source, card_selected = selection
			self._set_source(source)
			self._emit_status(f"Selected {card_selected.rank}{SUIT_SYMBOL[card_selected.suit]} in column {col_idx + 1}")
			return

		self._try_move((SLOT_TABLEAU, col_idx))

	def _resolve_tableau_selection(self, col_idx: int, pos: tuple) -> tuple[tuple, Card] | None:
		col_cards = self.state.tableau[col_idx]
		top_card = col_cards[-1]
		source = (SLOT_TABLEAU, col_idx)

		if len(pos) != 3:
			return source, top_card

		card_idx = pos[2]
		if col_cards[card_idx] in self._movable_bases(col_cards):
			return pos, col_cards[card_idx]
		if card_idx != len(col_cards) - 1:
			self._emit_status("Cannot move this card.")
			return None
		return source, top_card

	def _movable_bases(self, col_cards: tuple) -> set[Card]:
		return {sequence[0] for sequence in get_movable_sequences(col_cards)}

	def _on_card_double_clicked(self, pos: tuple):
		if self.state is None:
			return

		from_pos_engine = self._resolve_double_click_source(pos)
		if from_pos_engine is None:
			return

		valid_moves = get_valid_moves(self.state, prune_safe=False)

		foundation_move = self._find_first_move(valid_moves, from_pos_engine, SLOT_FOUNDATION)
		if foundation_move is not None:
			self._apply_automatic_move(foundation_move, "Automatically moved card to Foundation.", check_goal=True)
			return

		freecell_move = self._find_first_move(valid_moves, from_pos_engine, SLOT_FREECELL)
		if freecell_move is not None:
			self._apply_automatic_move(freecell_move, "Automatically moved to FreeCell.", check_goal=False)

	def _resolve_double_click_source(self, pos: tuple) -> tuple[str, int] | None:
		if len(pos) == 3:
			col_idx = pos[1]
			card_idx = pos[2]
			if card_idx == len(self.state.tableau[col_idx]) - 1:
				return (SLOT_TABLEAU, col_idx)
			return None

		if len(pos) == 2:
			return (pos[0], pos[1])

		return None

	def _on_tableau_target_clicked(self, col_idx: int):
		if self.selected_source is None:
			card = self.state.tableau[col_idx][-1] if self.state.tableau[col_idx] else None
			if card is None:
				self._emit_status("Column is empty. Select a source card first.")
				return
			self._set_source((SLOT_TABLEAU, col_idx))
			self._emit_status(f"Selected {card.rank}{SUIT_SYMBOL[card.suit]} in column {col_idx + 1}")
			return

		self._try_move((SLOT_TABLEAU, col_idx))

	def _on_freecell_clicked(self, cell_idx: int):
		if self.selected_source is None:
			card = self.state.freecells[cell_idx]
			if card is None:
				self._emit_status("FreeCell is empty.")
				return
			self._set_source((SLOT_FREECELL, cell_idx))
			self._emit_status(f"Selected {card.rank}{SUIT_SYMBOL[card.suit]} in FreeCell {cell_idx + 1}")
			return

		self._try_move((SLOT_FREECELL, cell_idx))

	def _on_foundation_clicked(self, foundation_idx: int):
		if self.selected_source is None:
			self._emit_status("Select a source card before moving to Foundation.")
			return
		self._try_move((SLOT_FOUNDATION, foundation_idx))
