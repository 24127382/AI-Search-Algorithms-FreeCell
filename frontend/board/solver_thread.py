"""Background Qt thread wrapper for running search algorithms."""

from backend.solver.algorithms import SearchAlgorithm
from frontend.shared.qt import QThread, Signal


class SolverThread(QThread):
	"""Run one solver invocation off the UI thread and emit result signals."""

	result_ready = Signal(object)
	error_occurred = Signal(str)

	def __init__(self, state, algo):
		"""Store immutable solve inputs used by thread run.

		Args:
			state: Initial state snapshot.
			algo: Solver key.
		"""
		super().__init__()
		self.state = state
		self.algo = algo

	def stop(self, timeout_ms: int = 250):
		"""Stop the running worker thread.

		Args:
			timeout_ms: Time to wait for graceful stop before forced terminate.
		"""
		self.requestInterruption()
		if not self.isRunning():
			self.state = None
			return

		if not self.wait(timeout_ms):
			self.terminate()
			self.wait(500)

		self.state = None
		self.algo = None

	def run(self):
		"""Execute solver and emit either path or formatted error message."""
		try:
			if self.isInterruptionRequested():
				return
			solver = SearchAlgorithm(self.state, should_cancel=self.isInterruptionRequested)
			path = solver.search(self.algo)
			if self.isInterruptionRequested():
				return
			self.result_ready.emit(path)
		except Exception as exc:
			if self.isInterruptionRequested():
				return
			self.error_occurred.emit(str(exc))
		finally:
			self.state = None
			self.algo = None
