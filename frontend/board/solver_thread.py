"""Background Qt thread wrapper for running search algorithms."""

from backend.solver.algorithms import SearchAlgorithm
from frontend.shared.qt import QThread, Signal


class SolverThread(QThread):
	"""Run one solver invocation off the UI thread and emit result signals."""

	result_ready = Signal(object)  # Emits (path, feedback_message)
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
		self.solver = None  # Keep reference to algorithm instance

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
		self.solver = None

	def run(self):
		"""Execute solver and emit either path or formatted error message."""
		try:
			if self.isInterruptionRequested():
				return
			self.solver = SearchAlgorithm(self.state, should_cancel=self.isInterruptionRequested)
			path = self.solver.search(self.algo)
			if self.isInterruptionRequested():
				return
			
			# Extract user feedback from the algorithm instance (if available)
			feedback = self._extract_feedback(path)
			
			# Emit tuple: (path, feedback_message)
			self.result_ready.emit((path, feedback))
		except Exception as exc:
			if self.isInterruptionRequested():
				return
			self.error_occurred.emit(str(exc))
		finally:
			self.state = None
			self.algo = None
			self.solver = None

	def _extract_feedback(self, path):
		"""Extract user-friendly feedback from the algorithm instance.
		
		Args:
			path: Result from search (None if failed or stopped).
			
		Returns:
			str: Feedback message, or None if no special feedback.
		"""
		if not self.solver:
			return None
		
		# Get the concrete algorithm instance
		algo_instance = self.solver.get_algorithm_instance(self.algo)
		
		if algo_instance is None:
			return None
		
		# Try to get user feedback from the algorithm
		if hasattr(algo_instance, "get_user_feedback"):
			try:
				feedback = algo_instance.get_user_feedback()
				return feedback if feedback else None
			except Exception:
				return None
		
		return None
