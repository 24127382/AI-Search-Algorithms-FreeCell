from backend.model.models import VALID_SUITS
from backend.rule.rules import get_movable_sequences
from frontend.board.constants import SLOT_FOUNDATION, SLOT_FREECELL, SLOT_TABLEAU
from frontend.card import CardWidget, SUIT_SYMBOL
from frontend.shared.animation import fade_in

class BoardUiRenderMixin:
	def _update_card_widget(self, card, new_parent, new_pos, pos_tuple, payload_str, is_draggable, drag_sequence, is_selected):
		from frontend.shared.animation import animate_move
		cw = self._card_registry.get(card)
		if isinstance(new_pos, tuple):
			try:
				from PySide6.QtCore import QPoint
			except ImportError:
				from PyQt6.QtCore import QPoint
			new_pos = QPoint(int(new_pos[0]), int(new_pos[1]))
		if cw is None:
			cw = CardWidget(card, pos_tuple, new_parent)
			cw.clicked.connect(self._on_card_clicked_dispatcher)
			cw.double_clicked.connect(self._on_card_double_clicked)
			cw.drop_received.connect(self._on_drop_received)
			self._card_registry[card] = cw
			cw.move(new_pos)
			cw.show()
			fade_in(cw, duration=120)
		else:
			cw.position = pos_tuple
			old_parent = cw.parent()
			if old_parent != new_parent and old_parent is not None:
				old_global = old_parent.mapToGlobal(cw.pos())
				cw.setParent(new_parent)
				start_pos = new_parent.mapFromGlobal(old_global)
				cw.move(start_pos)
				cw.show()
			elif old_parent is None:
				cw.setParent(new_parent)
				cw.move(new_pos)
				cw.show()

			if cw.pos() != new_pos:
				animate_move(cw, cw.pos(), new_pos, duration=165)
			else:
				cw.move(new_pos)

		cw.set_drag_payload(payload_str, is_draggable, drag_sequence)
		cw.set_selected(is_selected)
		cw.raise_()

	def _render(self):
		if self.state is None:
			return

		self.setUpdatesEnabled(False)
		try:
			self._render_freecells()
			self._render_foundations()
			self._render_tableau()
		finally:
			self.setUpdatesEnabled(True)
			self.update()

		self.move_count_changed.emit(self.move_count)

	def _emit_status(self, message: str):
		self.status_changed.emit(message)

	def _render_freecells(self):
		for idx, button in enumerate(self._freecell_buttons):
			card = self.state.freecells[idx]
			selected = self.selected_source == (SLOT_FREECELL, idx)

			if card:
				bg = "#f8f9fa"
				color = "#c0392b" if card.suit in ("hearts", "diamonds") else "#f7f8fa"
				border = "4px solid #ffeb3b" if selected else "1px solid #2c3e50"
				self._update_card_widget(card, button, (0, 0), (SLOT_FREECELL, idx), f"freecell:{idx}", True, [], selected)
			else:
				bg = "rgba(255,255,255,0)"
				color = "white"
				border = "4px solid #ffffff"

			button.set_drag_payload(f"freecell:{idx}", card is not None)
			button.setStyleSheet(
				f"text-align: center; border: {border}; background-color: {bg}; color: {color}; font-size: 14pt; border-radius: 8px;"
			)

	def _render_foundations(self):
		for idx, button in enumerate(self._foundation_buttons):
			foundation_cards = self.state.foundations[idx]
			top_card = foundation_cards[-1] if foundation_cards else None
			required_suit = VALID_SUITS[idx]
			target_symbol = SUIT_SYMBOL[required_suit]
			button.set_drag_payload("", False)

			if top_card:
				button.setText("")
				bg = "#f8f9fa"
				color = "#c0392b" if top_card.suit in ("hearts", "diamonds") else "#1f2d3d"
				border = "1px solid #2c3e50"
				font_size = "14px"
				for card in foundation_cards:
					self._update_card_widget(card, button, (0, 0), (SLOT_FOUNDATION, idx), "", False, [], False)
			else:
				button.setText(target_symbol)
				bg = "rgba(255,255,255,0)"
				color = "#c0392b" if required_suit in ("hearts", "diamonds") else "black"
				border = "4px solid #ffffff"
				font_size = "32px"

			button.setStyleSheet(
				f"text-align: center; border: {border}; background-color: {bg}; color: {color}; font-size: {font_size}; border-radius: 8px;"
			)

	def _render_tableau(self):
		for col_idx, col_cards in enumerate(self.state.tableau):
			movable_bases = {sequence[0] for sequence in get_movable_sequences(col_cards)}

			for card_idx, card in enumerate(col_cards):
				is_top = card_idx == len(col_cards) - 1
				is_draggable = card in movable_bases
				drag_sequence = col_cards[card_idx:] if is_draggable else []
				is_selected = self._is_selected_tableau_card(col_idx, card_idx, is_draggable, is_top)

				self._update_card_widget(
					card,
					self._tableau_layouts[col_idx],
					(0, card_idx * 30),
					(SLOT_TABLEAU, col_idx, card_idx),
					f"tableau:{col_idx}:{card_idx}",
					is_draggable,
					drag_sequence,
					is_selected,
				)

			col_selected = self.selected_source == (SLOT_TABLEAU, col_idx)
			border = "3px solid #ffeb3b" if col_selected else "4px solid #ffffff"
			self._tableau_buttons[col_idx].set_drag_payload(f"tableau:{col_idx}", bool(col_cards))
			self._tableau_buttons[col_idx].setStyleSheet(f"border: {border};")

	def _is_selected_tableau_card(self, col_idx: int, card_idx: int, is_draggable: bool, is_top: bool) -> bool:
		if not is_draggable or not self.selected_source:
			return False
		if self.selected_source[:2] != (SLOT_TABLEAU, col_idx):
			return False
		if len(self.selected_source) == 3:
			return self.selected_source[2] == card_idx
		return len(self.selected_source) == 2 and is_top
