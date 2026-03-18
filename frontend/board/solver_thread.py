"""Background Qt thread wrapper for running search algorithms."""

from backend.solver.algorithms import SearchAlgorithm
from frontend.shared.qt import QThread, Signal


class SolverThread(QThread):
	"""Run one solver invocation off the UI thread and emit result signals."""

	result_ready = Signal(object)
	error_occurred = Signal(str)

	def __init__(self, state, algo, ucs_mode="speed"):
		"""Store immutable solve inputs used by thread run.

		Args:
			state: Initial state snapshot.
			algo: Solver key.
			ucs_mode: UCS mode key.
		"""
		super().__init__()
		self.state = state
		self.algo = algo
		self.ucs_mode = ucs_mode

	def run(self):
		"""Execute solver and emit either path or formatted error message."""
		try:
			solver = SearchAlgorithm(self.state, mode=self.ucs_mode)
			path = solver.search(self.algo)
			self.result_ready.emit(path)
		except Exception as exc:
			self.error_occurred.emit(str(exc))
