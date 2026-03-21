"""Solver orchestration, replay, and game control helpers for the board."""

import time
from copy import deepcopy

from backend.engine.engine import apply_move, get_valid_moves
from frontend.card.assets import SUIT_SYMBOL
from frontend.board.solver_thread import SolverThread
from frontend.shared.qt import QTimer


class BoardSolverMixin:
	"""Provides undo/restart and background-solver integration behaviors."""

	def _stop_solver_execution(self) -> bool:
		"""Stop active solver worker and replay timer, if any.

		Returns:
			bool: True if any running solver activity was stopped.
		"""
		stopped_any = False

		if hasattr(self, "solve_timer") and self.solve_timer:
			self.solve_timer.stop()
			self.solve_timer = None
			stopped_any = True

		if hasattr(self, "solve_path"):
			self.solve_path = []

		had_running_solver = self.solver_thread is not None or self.is_solving

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
	def _solver_label(algo: str, ucs_mode: str) -> str:
		"""Build user-friendly solver label.

		Args:
			algo: Solver key.
			ucs_mode: UCS mode key.

		Returns:
			str: Display label.
		"""
		if algo == "UCS":
			mode_label = {
				"first": "First Solution",
				"speed": "Speed + Cost",
				"memory": "Exact Memory",
				"fast": "Speed + Cost",
				"exact": "Exact Memory",
			}.get(ucs_mode, ucs_mode)
			return f"UCS ({mode_label})"
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

	def solve_with_algo(self, algo: str, ucs_mode: str = "speed"):
		"""Start background solve job and prepare replay callbacks.

		Args:
			algo: Solver key to run.
			ucs_mode: UCS mode key when `algo` is UCS.
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
		solver_label = self._solver_label(algo, ucs_mode)
		self._emit_status(f"Solving with {solver_label}...")
		run_id = self._active_solver_run_id + 1
		self._active_solver_run_id = run_id

		self.solver_thread = SolverThread(self.state, algo, ucs_mode=ucs_mode)
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
		try:
			elapsed = time.perf_counter() - self._solve_started_at if self._solve_started_at else 0.0
			if not path:
				self._emit_status(f"{algo} failed to find a solution after {elapsed:.1f}s.")
				return

			self._emit_status(f"Found a solution in {len(path)} moves ({elapsed:.1f}s). Replaying...")

			self.solve_path = path
			self.solve_timer = QTimer(self)
			self.solve_timer.timeout.connect(self._replay_next_solver_move)
			self.solve_timer.start(140)
		except Exception as e:
			self._emit_status(f"Error processing solver result: {e}")
			import traceback
			traceback.print_exc()

	def _replay_next_solver_move(self):
		"""Apply one solver move per timer tick until path is exhausted."""
		try:
			if not hasattr(self, "solve_path") or not self.solve_path:
				if hasattr(self, "solve_timer") and self.solve_timer:
					self.solve_timer.stop()
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
				self.game_won.emit()
				self._emit_status("You won!")
		except Exception as e:
			if hasattr(self, "solve_timer") and self.solve_timer:
				self.solve_timer.stop()
			self._emit_status(f"Error replaying solution: {e}")
			import traceback
			traceback.print_exc()
	
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
