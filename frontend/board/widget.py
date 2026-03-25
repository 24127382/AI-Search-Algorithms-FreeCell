"""Concrete board widget composed from UI, interaction, and solver mixins."""

from copy import deepcopy

from backend.engine.shuffle import deal_by_game_number, random_deal_number
from backend.model.state import State
from frontend.board.move_interaction_mixin import BoardMoveInteractionMixin
from frontend.board.move_core_mixin import BoardMoveCoreMixin
from frontend.board.solver_mixin import BoardSolverMixin
from frontend.board.ui_render_mixin import BoardUiRenderMixin
from frontend.board.ui_layout_mixin import BoardUiLayoutMixin
from frontend.shared.qt import Signal, QWidget


class BoardWidget(BoardUiRenderMixin, BoardUiLayoutMixin, BoardMoveInteractionMixin, BoardMoveCoreMixin, BoardSolverMixin, QWidget):
	"""Central FreeCell board component.

	Attributes:
		state: Current backend state.
		initial_state: Snapshot used by restart.
		history: Stack of previous states for undo.
	"""

	status_changed = Signal(str)
	move_count_changed = Signal(int)
	game_won = Signal()
	deal_number_changed = Signal(int)
	solver_running_changed = Signal(bool)

	def __init__(self, deal_number: int | None = None, parent=None):
		"""Initialize board internals, build UI, and start first deal.

		Args:
			deal_number: Optional fixed Microsoft deal number.
			parent: Optional parent widget.
		"""
		super().__init__(parent)
		self.state: State | None = None
		self.initial_state: State | None = None
		self.history: list[State] = []
		self.selected_source: tuple | None = None
		self.move_count = 0
		self.requested_deal_number: int | None = deal_number
		self.current_deal_number: int | None = None
		self.solver_thread = None
		self.is_solving = False
		self._solve_started_at = 0.0
		self._active_solver_run_id = 0
		self.solve_timer = None
		self.solve_path = []
		self._solve_review_mode = False
		self._solve_is_playing = False
		self._solve_moves = []
		self._solve_states = []
		self._solve_current_index = 0
		self._solve_initial_state = None
		self._solve_base_move_count = 0
		self._solve_move_list_dialog = None
		self._solve_move_list_scroll = None
		self._solve_move_buttons = []
		self._solver_review_controls = None
		self._list_moves_button = None
		self._solver_prev_button = None
		self._solver_play_pause_button = None
		self._solver_next_button = None
		self._pre_win_snapshot = None
		self._last_announced_win_board_code = None

		self._freecell_buttons = []
		self._foundation_buttons = []
		self._tableau_buttons = []
		self._tableau_layouts = []
		self._card_registry = {}
		self._deal_number_label = None

		self._build_ui()
		self.new_game()

	def _build_initial_state(self) -> State:
		"""Create initial state for a new game.

		Returns:
			State: Freshly initialized game state.
		"""
		deal_number = self.requested_deal_number if self.requested_deal_number is not None else random_deal_number()
		tableau = deal_by_game_number(deal_number)
		self.current_deal_number = deal_number
		self.deal_number_changed.emit(deal_number)
		self._update_deal_number_label()
		return State.from_lists(tableau=tableau, freecells=[None] * 4, foundations=[[] for _ in range(4)])

	def _update_deal_number_label(self):
		"""Refresh on-board deal number text shown at bottom-left."""
		if self._deal_number_label is None:
			return
		if self.current_deal_number is None:
			self._deal_number_label.setText("Deal #-")
			return
		self._deal_number_label.setText(f"Deal #{self.current_deal_number}")

	def new_game(self):
		"""Reset game/session counters and render a new deal."""
		solver_stopped = self._stop_solver_execution()
		self._pre_win_snapshot = None
		self._last_announced_win_board_code = None
		self.initial_state = self._build_initial_state()
		self.state = deepcopy(self.initial_state)
		self.history.clear()
		self.move_count = 0
		self.selected_source = None
		self._render()
		if solver_stopped:
			self._emit_status(f"Solver stopped. New game started - Deal #{self.current_deal_number}.")
			return
		self._emit_status(f"New game started - Deal #{self.current_deal_number}.")

	def resizeEvent(self, event):
		"""Keep card widgets aligned/visible when the board is resized."""
		super().resizeEvent(event)
		if self.state is not None:
			self._render()

	def _capture_pre_win_snapshot(
		self,
		prev_state: State | None = None,
		prev_move_count: int | None = None,
		prev_history: list[State] | None = None,
	):
		"""Capture restorable board snapshot from immediately before a winning state.

		Args:
			prev_state: Explicit previous state to restore.
			prev_move_count: Explicit move count tied to previous state.
			prev_history: Explicit history stack tied to previous state.
		"""
		if prev_state is None:
			if self.history:
				prev_state = self.history[-1]
				prev_history = list(self.history[:-1]) if prev_history is None else prev_history
				prev_move_count = max(0, self.move_count - 1) if prev_move_count is None else prev_move_count
			elif self.initial_state is not None:
				prev_state = self.initial_state
				prev_history = [] if prev_history is None else prev_history
				prev_move_count = 0 if prev_move_count is None else prev_move_count

		if prev_state is None:
			return

		if prev_history is None:
			prev_history = list(self.history)
		if prev_move_count is None:
			prev_move_count = max(0, self.move_count - 1)

		self._pre_win_snapshot = {
			"state": prev_state,
			"history": list(prev_history),
			"move_count": max(0, prev_move_count),
			"selected_source": None,
		}

	def restore_previous_game_state(self) -> bool:
		"""Restore the board snapshot captured before the latest win.

		Returns:
			bool: `True` if a previous snapshot was restored.
		"""
		snapshot = self._pre_win_snapshot
		if snapshot is None:
			return False

		self.state = snapshot["state"]
		self.history = list(snapshot["history"])
		self.move_count = snapshot["move_count"]
		self.selected_source = snapshot["selected_source"]
		self._last_announced_win_board_code = None
		self._render()
		self._emit_status("Returned to the previous game state before win.")
		return True

	def _emit_game_won_once(self):
		"""Emit game-won signal once per unique goal board state."""
		if self.state is None:
			return
		board_code = self.state.board_code
		if self._last_announced_win_board_code == board_code:
			return
		self._last_announced_win_board_code = board_code
		self.game_won.emit()
