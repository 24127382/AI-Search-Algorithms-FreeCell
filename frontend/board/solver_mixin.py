"""Solver orchestration, replay, and game control helpers for the board."""

import time
from copy import deepcopy

from backend.engine.engine import apply_move, get_valid_moves
from frontend.card.assets import SUIT_SYMBOL
from frontend.board.solver_thread import SolverThread
from frontend.shared.qt import QDialog, QHBoxLayout, QLabel, QPushButton, QScrollArea, QTimer, QVBoxLayout, QWidget


class BoardSolverMixin:
	"""Provides undo/restart and background-solver integration behaviors."""

	def is_solver_mode_active(self) -> bool:
		"""Return whether solver-owned mode is active and manual card moves should be locked."""
		replay_running = bool(
			hasattr(self, "solve_timer")
			and self.solve_timer
			and self.solve_timer.isActive()
		)
		return bool(
			self.is_solving
			or self.solver_thread is not None
			or getattr(self, "_solve_review_mode", False)
			or getattr(self, "_solve_is_playing", False)
			or replay_running
		)

	def _emit_solver_interaction_locked(self):
		"""Emit status when player interaction is blocked by active solver mode."""
		self._emit_status("Solver is controlling the board. Press Stop to move cards manually.")

	def _set_solver_review_controls_visible(self, visible: bool):
		"""Show or hide solver review controls at the board bottom-right."""
		if getattr(self, "_solver_review_controls", None) is None:
			return
		self._solver_review_controls.setVisible(visible)

	def _set_solver_playing(self, is_playing: bool):
		"""Set play/pause state for solver review mode."""
		self._solve_is_playing = is_playing
		play_pause_button = getattr(self, "_solver_play_pause_button", None)
		if play_pause_button is not None:
			play_pause_button.setText("⏸" if is_playing else "▶")

	def _close_solver_move_list_dialog(self):
		"""Close and clear move list dialog references."""
		dialog = getattr(self, "_solve_move_list_dialog", None)
		if dialog is not None:
			dialog.close()
		self._solve_move_list_dialog = None
		self._solve_move_buttons = []
		self._solve_move_list_scroll = None

	def _on_solver_move_list_dialog_destroyed(self, _=None):
		"""Clear dialog references when user closes the move list window."""
		self._solve_move_list_dialog = None
		self._solve_move_buttons = []
		self._solve_move_list_scroll = None

	def _update_solver_move_list_highlight(self):
		"""Highlight currently selected move in the move list dialog."""
		buttons = getattr(self, "_solve_move_buttons", [])
		if not buttons:
			return

		for idx, button in enumerate(buttons, start=1):
			is_current = idx == self._solve_current_index
			if is_current:
				button.setStyleSheet(
					"text-align: left; padding: 6px 10px; "
					"background-color: rgba(255, 235, 59, 0.28); "
					"border: 2px solid rgba(255, 235, 59, 0.95);"
				)
			else:
				button.setStyleSheet("text-align: left; padding: 6px 10px;")

		scroll = getattr(self, "_solve_move_list_scroll", None)
		if scroll is not None and 1 <= self._solve_current_index <= len(buttons):
			scroll.ensureWidgetVisible(buttons[self._solve_current_index - 1])

	def _update_solver_review_controls(self):
		"""Refresh enabled/disabled state for solver review controls."""
		if not getattr(self, "_solve_review_mode", False):
			return

		move_count = len(self._solve_moves)
		at_start = self._solve_current_index <= 0
		at_end = self._solve_current_index >= move_count

		if self._list_moves_button is not None:
			self._list_moves_button.setEnabled(move_count > 0)
		if self._solver_prev_button is not None:
			self._solver_prev_button.setEnabled((not self._solve_is_playing) and (not at_start))
		if self._solver_next_button is not None:
			self._solver_next_button.setEnabled((not self._solve_is_playing) and (not at_end))
		if self._solver_play_pause_button is not None:
			self._solver_play_pause_button.setEnabled(move_count > 0 and (self._solve_is_playing or not at_end))

	def _format_solver_position(self, pos: tuple[str, int]) -> str:
		"""Format board position tuple into short user-facing text."""
		slot_type, index = pos
		if slot_type == "tableau":
			return f"Tableau {index + 1}"
		if slot_type == "freecell":
			return f"FreeCell {index + 1}"
		if slot_type == "foundation":
			return f"Foundation {index + 1}"
		return f"{slot_type} {index + 1}"

	def _describe_solver_move(self, move) -> str:
		"""Build concise description string for one solver move."""
		card_symbol = SUIT_SYMBOL.get(move.card.suit, "")
		card_label = f"{move.card.rank}{card_symbol}"
		if move.sequence and len(move.sequence) > 1:
			return f"Move {len(move.sequence)} cards ({card_label}) from {self._format_solver_position(move.from_pos)} → {self._format_solver_position(move.to_pos)}"
		return f"Move {card_label} from {self._format_solver_position(move.from_pos)} → {self._format_solver_position(move.to_pos)}"

	def _build_solver_states_from_path(self, path: list):
		"""Cache all intermediate states from initial state and solution path."""
		if not self._solve_initial_state:
			return
		self._solve_states = [self._solve_initial_state]
		state = self._solve_initial_state
		for move in path:
			state = apply_move(state, move)
			self._solve_states.append(state)

	def _go_to_solver_state_index(self, index: int):
		"""Jump board to an absolute index in cached solve states."""
		if not self._solve_states:
			return

		was_goal = bool(self.state and self.state.is_goal)
		max_index = len(self._solve_states) - 1
		target_index = max(0, min(index, max_index))
		self._solve_current_index = target_index
		self.state = self._solve_states[target_index]
		self.move_count = self._solve_base_move_count + target_index
		self.selected_source = None
		self._render()
		self._update_solver_review_controls()
		self._update_solver_move_list_highlight()

		if (not was_goal) and self.state.is_goal:
			if target_index > 0:
				self._capture_pre_win_snapshot(
					prev_state=self._solve_states[target_index - 1],
					prev_move_count=self._solve_base_move_count + target_index - 1,
					prev_history=list(self.history),
				)
			self._emit_status("Congratulations! You won FreeCell.")
			self._emit_game_won_once()

	def _play_next_solver_state(self):
		"""Advance one move during continue mode; stop at final state."""
		if not self._solve_review_mode or not self._solve_is_playing:
			return

		if self._solve_current_index >= len(self._solve_moves):
			self._set_solver_playing(False)
			if self.solve_timer:
				self.solve_timer.stop()
			self._update_solver_review_controls()
			self._emit_status("Reached final solver state.")
			return

		self._go_to_solver_state_index(self._solve_current_index + 1)
		if self._solve_current_index >= len(self._solve_moves):
			self._set_solver_playing(False)
			if self.solve_timer:
				self.solve_timer.stop()
			self._update_solver_review_controls()
			self._emit_status("Reached final solver state.")

	def _on_solver_prev_clicked(self):
		"""Jump back by one solved move when not playing."""
		if not self._solve_review_mode or self._solve_is_playing:
			return
		self._go_to_solver_state_index(self._solve_current_index - 1)

	def _on_solver_next_clicked(self):
		"""Jump forward by one solved move when not playing."""
		if not self._solve_review_mode or self._solve_is_playing:
			return
		self._go_to_solver_state_index(self._solve_current_index + 1)

	def _on_solver_play_pause_clicked(self):
		"""Toggle continue/pause for solver review playback."""
		if not self._solve_review_mode or not self._solve_moves:
			return

		if self._solve_is_playing:
			self._set_solver_playing(False)
			if self.solve_timer:
				self.solve_timer.stop()
			self._update_solver_review_controls()
			self._emit_status("Solver playback paused.")
			return

		if self._solve_current_index >= len(self._solve_moves):
			self._emit_status("Already at final solver state.")
			return

		if self.solve_timer is None:
			self.solve_timer = QTimer(self)
			self.solve_timer.timeout.connect(self._play_next_solver_state)
		self._set_solver_playing(True)
		self._update_solver_review_controls()
		self.solve_timer.start(300)
		self._emit_status("Solver playback running (0.3s per move).")

	def _jump_to_solver_move_from_dialog(self, step_index: int):
		"""Jump to selected move index from list dialog."""
		if self._solve_is_playing:
			return
		self._go_to_solver_state_index(step_index)
		self._emit_status(f"Jumped to move #{step_index}.")

	def _on_solver_list_moves_clicked(self):
		"""Open scrollable move list dialog and allow direct jump to any state."""
		if not self._solve_review_mode or not self._solve_moves:
			return

		existing_dialog = getattr(self, "_solve_move_list_dialog", None)
		if existing_dialog is not None and existing_dialog.isVisible():
			existing_dialog.raise_()
			existing_dialog.activateWindow()
			self._update_solver_move_list_highlight()
			return

		dialog = QDialog(self)
		dialog.setWindowTitle("List of move")
		dialog.resize(540, 420)
		dialog.destroyed.connect(self._on_solver_move_list_dialog_destroyed)
		self._solve_move_list_dialog = dialog

		root_layout = QVBoxLayout(dialog)
		root_layout.setContentsMargins(10, 10, 10, 10)
		root_layout.setSpacing(8)

		info_label = QLabel("Select a move to jump directly to that solver state.")
		root_layout.addWidget(info_label)

		scroll = QScrollArea(dialog)
		scroll.setWidgetResizable(True)
		self._solve_move_list_scroll = scroll
		list_container = QWidget()
		list_layout = QVBoxLayout(list_container)
		list_layout.setContentsMargins(4, 4, 4, 4)
		list_layout.setSpacing(6)
		self._solve_move_buttons = []

		for idx, move in enumerate(self._solve_moves, start=1):
			move_button = QPushButton(f"{idx}. {self._describe_solver_move(move)}")
			move_button.setStyleSheet("text-align: left; padding: 6px 10px;")
			move_button.clicked.connect(lambda _, step=idx: self._jump_to_solver_move_from_dialog(step))
			self._solve_move_buttons.append(move_button)
			list_layout.addWidget(move_button)

		list_layout.addStretch(1)
		scroll.setWidget(list_container)
		root_layout.addWidget(scroll)

		dialog_buttons = QHBoxLayout()
		dialog_buttons.addStretch(1)
		close_button = QPushButton("Close")
		close_button.clicked.connect(dialog.reject)
		dialog_buttons.addWidget(close_button)
		root_layout.addLayout(dialog_buttons)
		self._update_solver_move_list_highlight()

		dialog.show()

	def _stop_solver_execution(self) -> bool:
		"""Stop active solver worker and replay timer, if any.

		Returns:
			bool: True if any running solver activity was stopped.
		"""
		stopped_any = False
		had_running_replay = bool(
			hasattr(self, "solve_timer")
			and self.solve_timer
			and self.solve_timer.isActive()
		)
		had_running_review_mode = getattr(self, "_solve_review_mode", False)

		if hasattr(self, "solve_timer") and self.solve_timer:
			self.solve_timer.stop()
			self.solve_timer = None
			stopped_any = True

		if getattr(self, "_solve_is_playing", False):
			self._set_solver_playing(False)

		if hasattr(self, "solve_path"):
			self.solve_path = []
		self._solve_moves = []
		self._solve_states = []
		self._solve_current_index = 0
		self._solve_initial_state = None
		self._solve_review_mode = False
		self._close_solver_move_list_dialog()
		self._set_solver_review_controls_visible(False)
		self._update_solver_review_controls()

		had_running_solver = self.solver_thread is not None or self.is_solving or had_running_replay or had_running_review_mode

		if self.solver_thread is not None:
			self._active_solver_run_id += 1
			self.solver_thread.stop()
			self.solver_thread = None
			self.is_solving = False
			stopped_any = True

		if had_running_solver:
			self.solver_running_changed.emit(False)

		return stopped_any

	def stop_solver(self):
		"""Stop the currently running solver thread, if any."""
		if self._stop_solver_execution():
			self._emit_status("Solver stopped.")
			return
		self._emit_status("Solver is not running.")

	@staticmethod
	def _solver_label(algo: str) -> str:
		"""Build user-friendly solver label.

		Args:
			algo: Solver key.

		Returns:
			str: Display label.
		"""
		return algo

	def undo(self):
		"""Revert one move from history if available."""
		if not self.history:
			self._emit_status("No moves to undo.")
			return
		self.state = self.history.pop()
		self.move_count = max(0, self.move_count - 1)
		self.selected_source = None
		self._render()
		self._emit_status("Undid 1 move.")

	def solve_with_algo(self, algo: str):
		"""Start background solve job and prepare replay callbacks.

		Args:
			algo: Solver key to run.
		"""
		if self.state is None:
			return
		if self.is_solving:
			self._emit_status("A solver is already running. Please wait.")
			return
		self._stop_solver_execution()

		self.is_solving = True
		self.solver_running_changed.emit(True)
		self._solve_started_at = time.perf_counter()
		self._solve_initial_state = self.state
		self._solve_base_move_count = self.move_count
		solver_label = self._solver_label(algo)
		self._emit_status(f"Solving with {solver_label}...")
		run_id = self._active_solver_run_id + 1
		self._active_solver_run_id = run_id

		self.solver_thread = SolverThread(self.state, algo)
		self.solver_thread.result_ready.connect(lambda path, label=solver_label, current_run_id=run_id: self._on_solver_finished(label, path, current_run_id))
		self.solver_thread.error_occurred.connect(lambda error, label=solver_label, current_run_id=run_id: self._on_solver_error(label, error, current_run_id))
		self.solver_thread.finished.connect(lambda current_run_id=run_id: self._on_solver_thread_finished(current_run_id))
		self.solver_thread.start()

	def _on_solver_error(self, algo: str, error: str, run_id: int):
		"""Handle solver-thread failures and reset solving state.

		Args:
			algo: Solver label.
			error: Error message from solver thread.
			run_id: Solver invocation id used to ignore stale callbacks.
		"""
		if run_id != self._active_solver_run_id:
			return
		self._emit_status(f"{algo} error: {error}")
		self.is_solving = False
		self.solver_running_changed.emit(False)
		self.solver_thread = None

	def _on_solver_thread_finished(self, run_id: int):
		"""Clear thread reference after worker exits."""
		if run_id != self._active_solver_run_id:
			return
		self.is_solving = False
		replay_running = bool(
			hasattr(self, "solve_timer")
			and self.solve_timer
			and self.solve_timer.isActive()
		)
		if not replay_running and not self._solve_review_mode:
			self.solver_running_changed.emit(False)
		self.solver_thread = None

	def _on_solver_finished(self, algo, path, run_id: int):
		"""Receive solved path and start timed replay animation.

		Args:
			algo: Solver label.
			path: Solved move sequence.
			run_id: Solver invocation id used to ignore stale callbacks.
		"""
		if run_id != self._active_solver_run_id:
			return
		elapsed_ms = ((time.perf_counter() - self._solve_started_at) * 1000) if self._solve_started_at else 0.0
		if path is None:
			self._emit_status(f"{algo} failed to find a solution after {elapsed_ms:.0f}ms.")
			return

		if path == []:
			self._emit_status(f"{algo} reports already solved after {elapsed_ms:.0f}ms.")
			return

		self.solve_path = list(path)
		self._solve_moves = list(path)
		self._build_solver_states_from_path(self._solve_moves)
		self._solve_review_mode = True
		self._set_solver_playing(False)
		self._set_solver_review_controls_visible(True)
		self._go_to_solver_state_index(0)
		self.solver_running_changed.emit(True)
		self._emit_status(
			f"Found a solution in {len(path)} moves ({elapsed_ms:.0f}ms). Use List of move / Continue to review."
		)

	def _replay_next_solver_move(self):
		"""Apply one solver move per timer tick until path is exhausted."""
		if not hasattr(self, "solve_path") or not self.solve_path:
			if hasattr(self, "solve_timer") and self.solve_timer:
				self.solve_timer.stop()
				self.solve_timer = None
			self.solver_running_changed.emit(False)
			self._emit_status("Auto-solve complete.")
			return

		move = self.solve_path.pop(0)
		self.history.append(self.state)
		self.state = apply_move(self.state, move)
		self.move_count += 1

		self.move_count_changed.emit(self.move_count)
		self._render()

		if self.state.is_goal:
			if hasattr(self, "solve_timer") and self.solve_timer:
				self.solve_timer.stop()
				self.solve_timer = None
			self._capture_pre_win_snapshot()
			self.solver_running_changed.emit(False)
			self._emit_game_won_once()
			self._emit_status("You won!")
	
	def restart(self):
		"""Restore board to initial deal and clear transient runtime state."""
		if self.state is None:
			return
		if not getattr(self, "initial_state", None):
			self._emit_status("Cannot restart: initial state not available.")
			return
		solver_stopped = self._stop_solver_execution()

		self.state = deepcopy(self.initial_state)
		self.history.clear()
		self.move_count = 0
		self.selected_source = None
		self._render()
		if solver_stopped:
			self._emit_status("Solver stopped. Game restarted.")
			return
		self._emit_status("Game restarted.")

	def auto_to_foundation(self):
		"""Execute first legal move that sends a card to foundation."""
		if self.state is None:
			return

		for move in get_valid_moves(self.state, prune_safe=False):
			if move.to_pos[0] == "foundation":
				self._apply_automatic_move(move, "Automatically sent 1 card to Foundation.", check_goal=True)
				return

		self._emit_status("No cards can be moved to Foundation right now.")