from copy import deepcopy

from backend.engine.shuffle import deal, deal_by_game_number
from backend.model.state import State
from frontend.board.constants import DIFFICULTY_LEVELS
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
		self.initial_state: State | None = None
		self.history: list[State] = []
		self.selected_source: tuple | None = None
		self.move_count = 0
		self.difficulty = "medium"
		self.current_deal_number: int | None = None
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

	def _build_initial_state(self) -> State:
		# deal_number, tableau = deal(self.difficulty)
		tableau = deal_by_game_number(1)
		self.current_deal_number = 1
		return State.from_lists(tableau=tableau, freecells=[None] * 4, foundations=[[] for _ in range(4)])

	def set_difficulty(self, difficulty: str):
		normalized = (difficulty or "medium").strip().lower()
		if normalized not in DIFFICULTY_LEVELS:
			normalized = "medium"
		self.difficulty = normalized

	def new_game(self):
		self.initial_state = self._build_initial_state()
		self.state = deepcopy(self.initial_state)
		self.history.clear()
		self.move_count = 0
		self.selected_source = None
		self._render()
		self._emit_status(f"New game started ({self.difficulty.title()}) - Deal #{self.current_deal_number}.")
