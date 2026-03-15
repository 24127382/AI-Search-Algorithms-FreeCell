import time

from backend.engine.engine import apply_move, get_valid_moves, is_goal
from frontend.card import SUIT_SYMBOL
from frontend.board.solver_thread import SolverThread
from frontend.shared.qt import QTimer


class BoardSolverMixin:
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
		if hasattr(self, "solve_timer") and self.solve_timer:
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

		if is_goal(self.state):
			if hasattr(self, "solve_timer") and self.solve_timer:
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
		self._emit_status(f"Hint: {move.card.rank}{symbol} from {move.from_pos} -> {move.to_pos}")

	def auto_to_foundation(self):
		if self.state is None:
			return

		for move in get_valid_moves(self.state, prune_safe=False):
			if move.to_pos[0] == "foundation":
				self._apply_automatic_move(move, "Automatically sent 1 card to Foundation.", check_goal=True)
				return

		self._emit_status("No cards can be moved to Foundation right now.")
