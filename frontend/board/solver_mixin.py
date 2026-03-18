"""Solver orchestration, replay, and game control helpers for the board."""

import time
from copy import deepcopy

from backend.engine.engine import apply_move, get_valid_moves
from frontend.card.assets import SUIT_SYMBOL
from frontend.board.solver_thread import SolverThread
from frontend.shared.qt import QTimer


class BoardSolverMixin:
	"""Provides undo/restart and background-solver integration behaviors."""

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
		if hasattr(self, "solve_timer") and self.solve_timer:
			self.solve_timer.stop()
			self.solve_path = []

		self.is_solving = True
		self._solve_started_at = time.perf_counter()
		solver_label = self._solver_label(algo, ucs_mode)
		self._emit_status(f"Solving with {solver_label}...")

		self.solver_thread = SolverThread(self.state, algo, ucs_mode=ucs_mode)
		self.solver_thread.result_ready.connect(lambda path, label=solver_label: self._on_solver_finished(label, path))
		self.solver_thread.error_occurred.connect(lambda error, label=solver_label: self._on_solver_error(label, error))
		self.solver_thread.finished.connect(self._on_solver_thread_finished)
		self.solver_thread.start()

	def _on_solver_error(self, algo: str, error: str):
		"""Handle solver-thread failures and reset solving state.

		Args:
			algo: Solver label.
			error: Error message from solver thread.
		"""
		self._emit_status(f"{algo} error: {error}")
		self.is_solving = False
		self.solver_thread = None

	def _on_solver_thread_finished(self):
		"""Clear thread reference after worker exits."""
		self.is_solving = False
		self.solver_thread = None

	def _on_solver_finished(self, algo, path):
		"""Receive solved path and start timed replay animation.

		Args:
			algo: Solver label.
			path: Solved move sequence.
		"""
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
		"""Apply one solver move per timer tick until path is exhausted."""
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
	
	def restart(self):
		"""Restore board to initial deal and clear transient runtime state."""
		if self.state is None:
			return
		if not getattr(self, "initial_state", None):
			self._emit_status("Cannot restart: initial state not available.")
			return
		if self.is_solving:
			self._emit_status("Cannot restart while solver is running.")
			return
		if hasattr(self, "solve_timer") and self.solve_timer:
			self.solve_timer.stop()
			self.solve_path = []

		self.state = deepcopy(self.initial_state)
		self.history.clear()
		self.move_count = 0
		self.selected_source = None
		self._render()
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
