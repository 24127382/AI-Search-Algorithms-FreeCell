import random
import time

from backend.engine.engine import apply_move, get_valid_moves, is_goal
from backend.solver.algorithms import SearchAlgorithm
from backend.rule.rules import get_movable_sequences, get_max_sequence_length
from backend.model.models import Card, State, VALID_RANK, VALID_SUITS
from frontend.animation import fade_in
from frontend.card_widget import CardWidget, SUIT_SYMBOL
from frontend.qt_compat import (
	QThread,
	QTimer,
	QHBoxLayout,
	QLabel,
	QPushButton,
	QScrollArea,
	QSizePolicy,
	QVBoxLayout,
	QWidget,
	Qt,
	Signal,
	QDrag,
	QMimeData,
	QPixmap,
	QGraphicsOpacityEffect,
)

DIFFICULTY_LEVELS = ("easy", "medium", "hard", "expert")
DIFFICULTY_PERCENTILES = {
	"easy": 0.12,
	"medium": 0.42,
	"hard": 0.72,
	"expert": 0.92,
}
DIFFICULTY_SAMPLE_SIZE = 48

class SolverThread(QThread):
	result_ready = Signal(object)
	error_occurred = Signal(str)

	def __init__(self, state, algo):
		super().__init__()
		self.state = state
		self.algo = algo

	def run(self):
		try:
			solver = SearchAlgorithm(self.state)
			path = solver.search(self.algo)
			self.result_ready.emit(path)
		except Exception as e:
			self.error_occurred.emit(str(e))

class SlotButton(QPushButton):
	card_clicked = Signal(tuple)
	drop_received = Signal(tuple, tuple)

	def __init__(self, slot_type: str, slot_index: int, parent=None):
		super().__init__(parent)
		self.slot_type = slot_type
		self.slot_index = slot_index
		self._drag_enabled = False
		self._drag_payload = ""
		self._mouse_press_pos = None
		self._drag_started = False
		self.setAcceptDrops(True)

	def set_drag_payload(self, payload: str, enabled: bool):
		self._drag_payload = payload
		self._drag_enabled = enabled

	def mousePressEvent(self, event):
		if event.button() == Qt.MouseButton.LeftButton:
			self._mouse_press_pos = event.pos()
			self._drag_started = False
		super().mousePressEvent(event)

	def mouseMoveEvent(self, event):
		if not self._drag_enabled:
			super().mouseMoveEvent(event)
			return

		if not (event.buttons() & Qt.MouseButton.LeftButton):
			super().mouseMoveEvent(event)
			return

		if self._mouse_press_pos is None:
			super().mouseMoveEvent(event)
			return

		delta = event.pos() - self._mouse_press_pos
		if delta.manhattanLength() < 10:
			super().mouseMoveEvent(event)
			return

		drag = QDrag(self)
		mime = QMimeData()
		mime.setText(self._drag_payload)
		drag.setMimeData(mime)
		
		pixmap = QPixmap(self.size())
		pixmap.fill(Qt.GlobalColor.transparent)
		self.render(pixmap)
		drag.setPixmap(pixmap)
		drag.setHotSpot(event.pos())

		self._drag_started = True

		should_hide = False
		if self.slot_type == "freecell" and self._drag_payload and not self._drag_payload.endswith(":False"):
			should_hide = True
			
		if should_hide:
			effect = QGraphicsOpacityEffect(self)
			effect.setOpacity(0.0)
			self.setGraphicsEffect(effect)

		drag.exec(Qt.DropAction.MoveAction)

		if should_hide:
			try:
				self.setGraphicsEffect(None)
			except RuntimeError:
				pass

		super().mouseMoveEvent(event)

	def mouseReleaseEvent(self, event):
		if event.button() == Qt.MouseButton.LeftButton and not self._drag_started:
			source = (self.slot_type, self.slot_index)
			if self.slot_type in ("tableau", "freecell"):
				self.card_clicked.emit(source)
		super().mouseReleaseEvent(event)

	def dragEnterEvent(self, event):
		if event.mimeData().hasText() and ":" in event.mimeData().text():
			event.acceptProposedAction()
			return
		event.ignore()

	def dropEvent(self, event):
		text = event.mimeData().text()
		parts = text.split(":")
		if len(parts) >= 2:
			from_pos = (parts[0], int(parts[1]))
			if len(parts) == 3:
				from_pos = (parts[0], int(parts[1]), int(parts[2]))
			to_pos = (self.slot_type, self.slot_index)
			self.drop_received.emit(from_pos, to_pos)
			event.acceptProposedAction()
		else:
			event.ignore()


class TableauColumnWidget(QWidget):
	drop_received = Signal(tuple, tuple)

	def __init__(self, col_idx: int, parent=None):
		super().__init__(parent)
		self.col_idx = col_idx
		self.setAcceptDrops(True)
		self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

	def dragEnterEvent(self, event):
		if event.mimeData().hasText() and ":" in event.mimeData().text():
			event.acceptProposedAction()
			return
		event.ignore()

	def dropEvent(self, event):
		text = event.mimeData().text()
		parts = text.split(":")
		if len(parts) >= 2:
			from_pos = (parts[0], int(parts[1]))
			if len(parts) == 3:
				from_pos = (parts[0], int(parts[1]), int(parts[2]))
			to_pos = ("tableau", self.col_idx)
			self.drop_received.emit(from_pos, to_pos)
			event.acceptProposedAction()
		else:
			event.ignore()


class BoardWidget(QWidget):
	status_changed = Signal(str)
	move_count_changed = Signal(int)
	game_won = Signal()

	def __init__(self, difficulty: str = "medium", parent=None):
		super().__init__(parent)
		self.state: State | None = None
		self.history: list[State] = []
		self.selected_source: tuple[str, int] | None = None
		self.move_count = 0
		self.difficulty = "medium"
		self.set_difficulty(difficulty)
		self.solver_thread: SolverThread | None = None
		self.is_solving = False
		self._solve_started_at = 0.0

		self._freecell_buttons: list[QPushButton] = []
		self._foundation_buttons: list[QPushButton] = []
		self._tableau_buttons: list[QPushButton] = []
		self._tableau_layouts: list[TableauColumnWidget] = []
		self._card_registry: dict[Card, CardWidget] = {}

		self._build_ui()
		self.new_game()

	def _build_ui(self):
		root_layout = QVBoxLayout(self)
		root_layout.setContentsMargins(14, 12, 14, 12)
		root_layout.setSpacing(9)
		self.setStyleSheet("""
			QLabel {
				color: #f3f8f4;
			}
			QPushButton {
				background-color: rgba(255, 255, 255, 0.07);
				border: 2px solid rgba(255, 255, 255, 0.35);
				border-radius: 8px;
				color: white;
				font-weight: bold;
			}
			QPushButton:hover {
				background-color: rgba(255, 255, 255, 0.14);
				border-color: white;
			}
		""")

		top_label = QLabel("FreeCells / Foundations")
		top_label.setStyleSheet("font-weight: 700; font-size: 14pt; letter-spacing: 0.5px;")
		root_layout.addWidget(top_label)

		top_row = QHBoxLayout()
		top_row.setSpacing(14)
		top_row.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
		top_row.addStretch()

		for index in range(4):
			button = SlotButton("FreeCell", index)
			button.setFixedSize(64, 86)
			button.clicked.connect(lambda _, idx=index: self._on_freecell_clicked(idx))
			button.card_clicked.connect(self._on_slot_source_clicked)
			button.drop_received.connect(self._on_drop_received)
			self._freecell_buttons.append(button)
			top_row.addWidget(button)

		# Expand spacer to match Tableau design below
		spacer = QLabel(" ")
		spacer.setFixedWidth(24)
		top_row.addWidget(spacer)

		for index in range(4):
			button = SlotButton("Foundation", index)
			button.setFixedSize(64, 86)
			button.clicked.connect(lambda _, idx=index: self._on_foundation_clicked(idx))
			button.drop_received.connect(self._on_drop_received)
			self._foundation_buttons.append(button)
			top_row.addWidget(button)

		top_row.addStretch()
		root_layout.addLayout(top_row)

		tableau_title = QLabel("Tableau")
		tableau_title.setStyleSheet("font-weight: 700; font-size: 14pt; letter-spacing: 0.5px;")
		tableau_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
		root_layout.addWidget(tableau_title)

		tableau_container = QWidget()
		root_layout.addWidget(tableau_container, 1)

		tableau_row = QHBoxLayout(tableau_container)
		tableau_row.setContentsMargins(0, 0, 0, 0)
		tableau_row.setSpacing(14)
		tableau_row.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
		tableau_row.addStretch()

		for col_idx in range(8):
			col_widget = TableauColumnWidget(col_idx)
			col_widget.drop_received.connect(self._on_drop_received)
			
			col_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
			col_widget.setFixedWidth(64)
			
			target_button = SlotButton("Tableau", col_idx)
			target_button.setText("")
			target_button.clicked.connect(lambda _, idx=col_idx: self._on_tableau_target_clicked(idx))
			target_button.card_clicked.connect(self._on_slot_source_clicked)
			target_button.drop_received.connect(self._on_drop_received)
			target_button.setParent(col_widget)
			target_button.move(0, 0)
			target_button.setFixedSize(64, 86)
			
			self._tableau_buttons.append(target_button)
			self._tableau_layouts.append(col_widget)
			tableau_row.addWidget(col_widget)
			
			if col_idx == 3:
				bottom_spacer = QLabel(" ")
				bottom_spacer.setFixedWidth(24)
				tableau_row.addWidget(bottom_spacer)

		tableau_row.addStretch()

	def _build_state_from_deck(self, deck: list[Card]) -> State:
		tableau = [[] for _ in range(8)]
		for index, card in enumerate(deck):
			tableau[index % 8].append(card)

		freecells = [None, None, None, None]
		foundations = [[], [], [], []]
		return State(tableau, freecells, foundations)

	def _estimate_difficulty_score(self, state: State) -> float:
		valid_moves = get_valid_moves(state, prune_safe=False)
		immediate_foundation_moves = sum(1 for move in valid_moves if move.to_pos[0] == "foundation")
		mobility = len(valid_moves)

		movable_sequence_count = 0
		max_sequence_len = 1
		for column in state.tableau:
			sequences = get_movable_sequences(column)
			movable_sequence_count += len(sequences)
			if sequences:
				max_sequence_len = max(max_sequence_len, max(len(seq) for seq in sequences))

		blocked_aces = 0
		buried_low_cards = 0
		for column in state.tableau:
			for idx, card in enumerate(column):
				is_top = idx == len(column) - 1
				if card.rank == "A" and not is_top:
					blocked_aces += 1
				if card.rank in ("A", "2", "3") and not is_top:
					buried_low_cards += 1

		score = (
			100.0
			+ blocked_aces * 6.0
			+ buried_low_cards * 2.0
			- immediate_foundation_moves * 4.0
			- mobility * 1.1
			- max_sequence_len * 2.0
			- movable_sequence_count * 0.4
		)
		return score

	def _build_initial_state(self) -> State:
		target_percentile = DIFFICULTY_PERCENTILES.get(self.difficulty, DIFFICULTY_PERCENTILES["medium"])
		scored_states: list[tuple[float, State]] = []

		for _ in range(DIFFICULTY_SAMPLE_SIZE):
			deck = [Card(suit=suit, rank=rank) for suit in VALID_SUITS for rank in VALID_RANK]
			random.shuffle(deck)
			candidate_state = self._build_state_from_deck(deck)
			candidate_score = self._estimate_difficulty_score(candidate_state)
			scored_states.append((candidate_score, candidate_state))

		scored_states.sort(key=lambda pair: pair[0])
		target_index = int(round((len(scored_states) - 1) * target_percentile))
		target_index = max(0, min(target_index, len(scored_states) - 1))
		return scored_states[target_index][1]


	def _on_card_clicked_dispatcher(self, pos: tuple):
		if pos[0] == "Tableau":
			self._on_tableau_card_clicked(pos)
		elif pos[0] == "FreeCell":
			self._on_freecell_clicked(pos[1])
		elif pos[0] == "Foundation":
			self._on_foundation_clicked(pos[1])

	def _update_card_widget(self, card, new_parent, new_pos, pos_tuple, payload_str, is_draggable, drag_sequence, is_top, is_selected):
		from frontend.animation import animate_move
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
			for idx, button in enumerate(self._freecell_buttons):
				card = self.state.freecells[idx]
				selected = self.selected_source == ("freecell", idx)

				if card:
					bg = "#f8f9fa"
					color = "#c0392b" if card.suit in ('hearts', 'diamonds') else "#f7f8fa"
					border = "4px solid #ffeb3b" if selected else "1px solid #2c3e50"
					self._update_card_widget(card, button, (0, 0), ("freecell", idx), f"freecell:{idx}", True, [], True, selected)
				else:
					bg = "rgba(255,255,255,0)"
					color = "white"
					border = "4px solid #ffffff" 
				button.set_drag_payload(f"freecell:{idx}", card is not None)
				button.setStyleSheet(f"text-align: center; border: {border}; background-color: {bg}; color: {color}; font-size: 14pt; border-radius: 8px;")

			for idx, button in enumerate(self._foundation_buttons):
				fnd_cards = self.state.foundations[idx]
				top_card = fnd_cards[-1] if fnd_cards else None
				required_suit = VALID_SUITS[idx]
				target_sym = SUIT_SYMBOL[required_suit]
				button.set_drag_payload("", False)

				if top_card:
					button.setText("")
					bg = "#f8f9fa"
					color = "#c0392b" if top_card.suit in ('hearts', 'diamonds') else "#1f2d3d"
					border = "1px solid #2c3e50"
					font_size = "14px"
					for c_idx, c in enumerate(fnd_cards):
						is_top = (c_idx == len(fnd_cards) - 1)
						self._update_card_widget(c, button, (0, 0), ("foundation", idx), "", False, [], is_top, False)
				else:
					button.setText(f"{target_sym}")
					bg = "rgba(255,255,255,0)"
					color = "#c0392b" if required_suit in ('hearts', 'diamonds') else "black"
					border = "4px solid #ffffff"
					font_size = "32px"

				button.setStyleSheet(f"text-align: center; border: {border}; background-color: {bg}; color: {color}; font-size: {font_size}; border-radius: 8px;")

			for col_idx, col_cards in enumerate(self.state.tableau):
				movable_bases = set()
				for seq in get_movable_sequences(col_cards):
					movable_bases.add(seq[0])

				for card_idx, card in enumerate(col_cards):
					is_top = card_idx == len(col_cards) - 1
					is_draggable = card in movable_bases
					drag_sequence = col_cards[card_idx:] if is_draggable else []
					
					is_selected = False
					if is_draggable and self.selected_source and self.selected_source[:2] == ("tableau", col_idx):
						if len(self.selected_source) == 3 and self.selected_source[2] == card_idx:
							is_selected = True
						elif len(self.selected_source) == 2 and is_top:
							is_selected = True
					
					self._update_card_widget(card, self._tableau_layouts[col_idx], (0, card_idx * 30), ("tableau", col_idx, card_idx), f"tableau:{col_idx}:{card_idx}", is_draggable, drag_sequence, is_top, is_selected)

				col_selected = self.selected_source == ("tableau", col_idx)
				border = "3px solid #ffeb3b" if col_selected else "4px solid #ffffff"
				self._tableau_buttons[col_idx].set_drag_payload(f"tableau:{col_idx}", bool(col_cards))
				self._tableau_buttons[col_idx].setStyleSheet(f"border: {border};")
		finally:
			self.setUpdatesEnabled(True)
			self.update()

		self.move_count_changed.emit(self.move_count)

	def _emit_status(self, message: str):
		self.status_changed.emit(message)

	def _on_slot_source_clicked(self, source: tuple[str, int]):
		source_type, source_idx = source
		if source_type == "Tableau":
			self._on_tableau_target_clicked(source_idx)
		elif source_type == "FreeCell":
			self._on_freecell_clicked(source_idx)

	def _on_drop_received(self, from_pos: tuple[str, int], to_pos: tuple[str, int]):
		self._apply_drop_move(from_pos, to_pos)

	def _apply_drop_move(self, from_pos: tuple[str, int], to_pos: tuple[str, int]):
		if self.state is None:
			return

		self.selected_source = from_pos
		self._try_move(to_pos)

	def _is_top_tableau_card(self, col_idx: int, card: Card) -> bool:
		column = self.state.tableau[col_idx]
		return bool(column) and column[-1] == card

	def _find_card_at_source(self, source: tuple[str, int]) -> Card | None:
		source_type, source_idx = source
		if source_type == "Tableau":
			column = self.state.tableau[source_idx]
			return column[-1] if column else None
		if source_type == "FreeCell":
			return self.state.freecells[source_idx]
		return None

	def _set_source(self, source: tuple[str, int] | None):
		self.selected_source = source
		self._render()

	def _try_move(self, to_pos: tuple[str, int]):
		if self.state is None or self.selected_source is None:
			return

		from_type = self.selected_source[0]
		from_idx = self.selected_source[1]
		from_pos_engine = (from_type.lower(), from_idx)
		
		# If user dragged a specific card deep in the column, let's target that exact card
		expected_card = None
		if len(self.selected_source) == 3 and from_type == "Tableau":
			card_idx = self.selected_source[2]
			if card_idx < len(self.state.tableau[from_idx]):
				expected_card = self.state.tableau[from_idx][card_idx]

		if from_pos_engine == to_pos[:2]:
			self._set_source(None)
			return

		candidate_move = None
		for move in get_valid_moves(self.state, prune_safe=False):
			if move.from_pos == (from_pos_engine[0], from_pos_engine[1]) and move.to_pos == (to_pos[0].lower(), to_pos[1]):
				if expected_card:
					if move.card == expected_card:
						candidate_move = move
						break
				else:
					# Find the first valid move (default behavior for single clicking without specific card)
					candidate_move = move
					break

		if candidate_move is None:
			# Check if they logically tried to drag a valid sequence but K limit was exceeded
			from_col_cards = self.state.tableau[from_idx] if from_type == "Tableau" else []
			target_seq = None
			if from_col_cards:
				for sq in get_movable_sequences(from_col_cards):
					if expected_card and sq[0] == expected_card:
						target_seq = sq
						break
			if target_seq:
				max_k = get_max_sequence_length(self.state)
				is_to_empty = False
				if to_pos[0] == "Tableau" and not self.state.tableau[to_pos[1]]:
					max_k = max_k // 2
					is_to_empty = True
				if len(target_seq) > max_k:
					empty_freecells = sum(1 for c in self.state.freecells if c is None)
					if is_to_empty:
						self._emit_status(f"FreeCell Rule: With {empty_freecells} empty Freecell(s), you can only move a MAXIMUM of {max_k} cards at once to an empty column!")
					else:
						self._emit_status(f"FreeCell Rule: You only have enough empty cells to move a maximum of {max_k} cards at once!")
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

	def _on_tableau_card_clicked(self, pos: tuple):
		if self.state is None:
			return

		# Pos could be (type, col_idx) or (type, col_idx, card_idx)
		col_idx = pos[1]
		
		if not self.state.tableau[col_idx]:
			return

		col_cards = self.state.tableau[col_idx]
		top_card = col_cards[-1]
		
		if self.selected_source is None:
			source = ("Tableau", col_idx)
			card_selected = top_card
			
			if len(pos) == 3:
				card_idx = pos[2]
				
				# Check if the clicked card is draggable
				movable_bases = set()
				for seq in get_movable_sequences(col_cards):
					movable_bases.add(seq[0])
						
				if col_cards[card_idx] in movable_bases:
					source = pos
					card_selected = col_cards[card_idx]
				elif card_idx != len(col_cards) - 1:
					# Ignored if clicking a deep unmovable card
					self._emit_status("Cannot move this card.")
					return
				
			self._set_source(source)
			self._emit_status(f"Selected {card_selected.rank}{SUIT_SYMBOL[card_selected.suit]} in column {col_idx + 1}")
			return

		self._try_move(("Tableau", col_idx))

	def _on_card_double_clicked(self, pos: tuple):
		if self.state is None:
			return
		
		# Double-click only makes sense for single cards (the top card of a tableau)
		# Or standard freecells
		from_pos_engine = None
		if len(pos) == 3:
			col_idx = pos[1]
			card_idx = pos[2]
			if card_idx == len(self.state.tableau[col_idx]) - 1:
				from_pos_engine = ("tableau", col_idx)
		elif len(pos) == 2:
			from_pos_engine = (pos[0].lower(), pos[1])
			
		if not from_pos_engine:
			return
			
		valid_moves = get_valid_moves(self.state, prune_safe=False)
		
		# 1. First try to move to foundation
		for move in valid_moves:
			if move.from_pos == from_pos_engine and move.to_pos[0] == "foundation":
				self.history.append(self.state)
				self.state = apply_move(self.state, move)
				self.move_count += 1
				self.selected_source = None
				self._emit_status(f"Automatically moved card to Foundation.")
				self._render()
				if is_goal(self.state):
					self._emit_status("Congratulations! You won FreeCell.")
					self.game_won.emit()
				return
				
		# 2. Then try to move to freecell if possible
		for move in valid_moves:
			if move.from_pos == from_pos_engine and move.to_pos[0] == "freecell":
				self.history.append(self.state)
				self.state = apply_move(self.state, move)
				self.move_count += 1
				self.selected_source = None
				self._emit_status(f"Automatically moved to FreeCell.")
				self._render()
				return

	def _on_tableau_target_clicked(self, col_idx: int):
		if self.selected_source is None:
			card = self.state.tableau[col_idx][-1] if self.state.tableau[col_idx] else None
			if card is None:
				self._emit_status("Column is empty. Select a source card first.")
				return
			self._set_source(("Tableau", col_idx))
			self._emit_status(f"Selected {card.rank}{SUIT_SYMBOL[card.suit]} in column {col_idx + 1}")
			return

		self._try_move(("Tableau", col_idx))

	def _on_freecell_clicked(self, cell_idx: int):
		if self.selected_source is None:
			card = self.state.freecells[cell_idx]
			if card is None:
				self._emit_status("FreeCell is empty.")
				return
			self._set_source(("FreeCell", cell_idx))
			self._emit_status(f"Selected {card.rank}{SUIT_SYMBOL[card.suit]} in FreeCell {cell_idx + 1}")
			return

		self._try_move(("FreeCell", cell_idx))

	def _on_foundation_clicked(self, foundation_idx: int):
		if self.selected_source is None:
			self._emit_status("Select a source card before moving to Foundation.")
			return
		self._try_move(("Foundation", foundation_idx))

	def set_difficulty(self, difficulty: str):
		normalized = (difficulty or "medium").strip().lower()
		if normalized not in DIFFICULTY_LEVELS:
			normalized = "medium"
		self.difficulty = normalized

	def new_game(self):
		self.state = self._build_initial_state()
		self.history.clear()
		self.move_count = 0
		self.selected_source = None
		self._render()
		self._emit_status(f"New game started ({self.difficulty.title()}).")

	def undo(self):
		if not self.history:
			self._emit_status("No moves to undo.")
			return
		self.state = self.history.pop()
		self.move_count = max(0, self.move_count - 1)
		self.selected_source = None
		self._render()
		self._emit_status("Undid 1 move.")

	
	def solve_with_algo(self, algo: str):
		if self.state is None: 
			return
		if self.is_solving:
			self._emit_status("A solver is already running. Please wait.")
			return
		if hasattr(self, 'solve_timer') and self.solve_timer:
			self.solve_timer.stop()
			self.solve_path = []

		self.is_solving = True
		self._solve_started_at = time.perf_counter()
		self._emit_status(f"Solving with {algo}...")
		
		self.solver_thread = SolverThread(self.state, algo)
		self.solver_thread.result_ready.connect(lambda path: self._on_solver_finished(algo, path))
		self.solver_thread.error_occurred.connect(lambda error: self._on_solver_error(algo, error))
		self.solver_thread.finished.connect(self._on_solver_thread_finished)
		self.solver_thread.start()

	def _on_solver_error(self, algo: str, error: str):
		self._emit_status(f"{algo} error: {error}")
		self.is_solving = False
		self.solver_thread = None

	def _on_solver_thread_finished(self):
		self.is_solving = False
		self.solver_thread = None

	def _on_solver_finished(self, algo, path):
		elapsed = time.perf_counter() - self._solve_started_at if self._solve_started_at else 0.0
		if not path:
			self._emit_status(f"{algo} failed to find a solution after {elapsed:.1f}s.")
			return
			
		self._emit_status(f"Found a solution in {len(path)} moves ({elapsed:.1f}s). Replaying...")
		
		self.solve_path = path
		self.solve_timer = QTimer(self)
		self.solve_timer.timeout.connect(self._replay_next_solver_move)
		self.solve_timer.start(140)

	def _replay_next_solver_move(self):
		if not hasattr(self, 'solve_path') or not self.solve_path:
			if hasattr(self, 'solve_timer') and self.solve_timer:
				self.solve_timer.stop()
			self._emit_status("Auto-solve complete.")
			return
			
		move = self.solve_path.pop(0)
		self.history.append(self.state)
		self.state = apply_move(self.state, move)
		self.move_count += 1
		
		self.move_count_changed.emit(self.move_count)
		self._render()

		if is_goal(self.state):
			if hasattr(self, 'solve_timer') and self.solve_timer:
				self.solve_timer.stop()
			self.game_won.emit()
			self._emit_status("You won!")

	def hint(self):
		if self.state is None:
			return

		valid_moves = get_valid_moves(self.state, prune_safe=False)
		if not valid_moves:
			self._emit_status("No valid moves available.")
			return

		move = valid_moves[0]
		symbol = SUIT_SYMBOL[move.card.suit]
		self._emit_status(
			f"Hint: {move.card.rank}{symbol} from {move.from_pos} -> {move.to_pos}"
		)

	def auto_to_foundation(self):
		if self.state is None:
			return

		for move in get_valid_moves(self.state, prune_safe=False):
			if move.to_pos[0] == "foundation":
				self.history.append(self.state)
				self.state = apply_move(self.state, move)
				self.move_count += 1
				self.selected_source = None
				self._render()
				self._emit_status("Automatically sent 1 card to Foundation.")
				if is_goal(self.state):
					self._emit_status("Congratulations! You won FreeCell.")
					self.game_won.emit()
				return

		self._emit_status("No cards can be moved to Foundation right now.")

