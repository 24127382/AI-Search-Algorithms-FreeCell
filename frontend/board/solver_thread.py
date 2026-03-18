from backend.solver.algorithms import SearchAlgorithm
from frontend.shared.qt import QThread, Signal


class SolverThread(QThread):
	result_ready = Signal(object)
	error_occurred = Signal(str)

	def __init__(self, state, algo, ucs_mode="speed"):
		super().__init__()
		self.state = state
		self.algo = algo
		self.ucs_mode = ucs_mode

	def run(self):
		try:
			solver = SearchAlgorithm(self.state, mode=self.ucs_mode)
			path = solver.search(self.algo)
			self.result_ready.emit(path)
		except Exception as exc:
			self.error_occurred.emit(str(exc))
