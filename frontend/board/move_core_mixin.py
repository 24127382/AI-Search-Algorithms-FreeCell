from backend.engine.engine import apply_move, get_valid_moves, is_goal
from backend.model.models import Card
from backend.rule.rules import get_max_sequence_length, get_movable_sequences
from frontend.board.constants import SLOT_TABLEAU
from frontend.card import SUIT_SYMBOL


class BoardMoveCoreMixin:
	def _on_drop_received(self, from_pos: tuple[str, int], to_pos: tuple[str, int]):
		self._apply_drop_move(from_pos, to_pos)

	def _apply_drop_move(self, from_pos: tuple[str, int], to_pos: tuple[str, int]):
		if self.state is None:
			return

		self.selected_source = from_pos
		self._try_move(to_pos)

	def _set_source(self, source: tuple | None):
		self.selected_source = source
		self._render()

	def _try_move(self, to_pos: tuple[str, int]):
		if self.state is None or self.selected_source is None:
			return

		from_pos_engine = (self.selected_source[0], self.selected_source[1])
		expected_card = self._expected_card_from_selected_source()
		if from_pos_engine == to_pos[:2]:
			self._set_source(None)
			return

		candidate_move = self._find_candidate_move(from_pos_engine, to_pos, expected_card)

		if candidate_move is None:
			if self._emit_sequence_limit_violation(to_pos, expected_card):
				self._set_source(None)
				return
			self._emit_status("Invalid move.")
			self._set_source(None)
			return

		self.history.append(self.state)
		self.state = apply_move(self.state, candidate_move)
		self.move_count += 1
		self._set_source(None)
		self._emit_status(
			f"Move: {candidate_move.card.rank}{SUIT_SYMBOL[candidate_move.card.suit]} "
			f"{candidate_move.from_pos} -> {candidate_move.to_pos}"
		)

		if is_goal(self.state):
			self._emit_status("Congratulations! You won FreeCell.")
			self.game_won.emit()

	def _expected_card_from_selected_source(self) -> Card | None:
		if self.selected_source is None:
			return None
		if len(self.selected_source) != 3 or self.selected_source[0] != SLOT_TABLEAU:
			return None

		from_idx = self.selected_source[1]
		card_idx = self.selected_source[2]
		if card_idx >= len(self.state.tableau[from_idx]):
			return None
		return self.state.tableau[from_idx][card_idx]

	def _find_candidate_move(self, from_pos: tuple[str, int], to_pos: tuple[str, int], expected_card: Card | None):
		for move in get_valid_moves(self.state, prune_safe=False):
			if move.from_pos != from_pos or move.to_pos != to_pos:
				continue
			if expected_card is None or move.card == expected_card:
				return move
		return None

	def _emit_sequence_limit_violation(self, to_pos: tuple[str, int], expected_card: Card | None) -> bool:
		if self.selected_source is None or self.selected_source[0] != SLOT_TABLEAU:
			return False

		from_idx = self.selected_source[1]
		from_col_cards = self.state.tableau[from_idx]
		target_sequence = None
		for sequence in get_movable_sequences(from_col_cards):
			if expected_card and sequence[0] == expected_card:
				target_sequence = sequence
				break

		if not target_sequence:
			return False

		max_k = get_max_sequence_length(self.state)
		is_to_empty_tableau = to_pos[0] == SLOT_TABLEAU and not self.state.tableau[to_pos[1]]
		if is_to_empty_tableau:
			max_k = max_k // 2

		if len(target_sequence) <= max_k:
			return False

		empty_freecells = sum(1 for card in self.state.freecells if card is None)
		if is_to_empty_tableau:
			self._emit_status(
				f"FreeCell Rule: With {empty_freecells} empty Freecell(s), you can only move a MAXIMUM of {max_k} cards at once to an empty column!"
			)
		else:
			self._emit_status(
				f"FreeCell Rule: You only have enough empty cells to move a maximum of {max_k} cards at once!"
			)
		return True

	def _find_first_move(self, valid_moves: list, from_pos: tuple[str, int], target_type: str):
		for move in valid_moves:
			if move.from_pos == from_pos and move.to_pos[0] == target_type:
				return move
		return None

	def _apply_automatic_move(self, move, status_message: str, check_goal: bool):
		self.history.append(self.state)
		self.state = apply_move(self.state, move)
		self.move_count += 1
		self.selected_source = None
		self._emit_status(status_message)
		self._render()

		if check_goal and is_goal(self.state):
			self._emit_status("Congratulations! You won FreeCell.")
			self.game_won.emit()
