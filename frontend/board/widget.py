import random

from backend.model.models import Card, State, VALID_RANK, VALID_SUITS
from backend.rule.rules import get_movable_sequences
from frontend.board.constants import DIFFICULTY_LEVELS, DIFFICULTY_PERCENTILES, DIFFICULTY_SAMPLE_SIZE
from frontend.board.move_interaction_mixin import BoardMoveInteractionMixin
from frontend.board.move_core_mixin import BoardMoveCoreMixin
from frontend.board.solver_mixin import BoardSolverMixin
from frontend.board.ui_render_mixin import BoardUiRenderMixin
from frontend.board.ui_layout_mixin import BoardUiLayoutMixin
from frontend.shared.qt import Signal, QWidget


class BoardWidget(BoardUiRenderMixin, BoardUiLayoutMixin, BoardMoveInteractionMixin, BoardMoveCoreMixin, BoardSolverMixin, QWidget):
	status_changed = Signal(str)
	move_count_changed = Signal(int)
	game_won = Signal()

	def __init__(self, difficulty: str = "medium", parent=None):
		super().__init__(parent)
		self.state: State | None = None
		self.history: list[State] = []
		self.selected_source: tuple | None = None
		self.move_count = 0
		self.difficulty = "medium"
		self.set_difficulty(difficulty)
		self.solver_thread = None
		self.is_solving = False
		self._solve_started_at = 0.0

		self._freecell_buttons = []
		self._foundation_buttons = []
		self._tableau_buttons = []
		self._tableau_layouts = []
		self._card_registry = {}

		self._build_ui()
		self.new_game()

	def _build_state_from_deck(self, deck: list[Card]) -> State:
		tableau = [[] for _ in range(8)]
		for index, card in enumerate(deck):
			tableau[index % 8].append(card)

		freecells = [None, None, None, None]
		foundations = [[], [], [], []]
		return State(tableau, freecells, foundations)

	def _estimate_difficulty_score(self, state: State) -> float:
		valid_moves = self._collect_valid_moves(state)
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

		return (
			100.0
			+ blocked_aces * 6.0
			+ buried_low_cards * 2.0
			- immediate_foundation_moves * 4.0
			- mobility * 1.1
			- max_sequence_len * 2.0
			- movable_sequence_count * 0.4
		)

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

	def _collect_valid_moves(self, state: State):
		from backend.engine.engine import get_valid_moves

		return get_valid_moves(state, prune_safe=False)

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
