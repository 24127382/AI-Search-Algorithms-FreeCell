"""Background Qt thread wrapper for running search algorithms."""

from backend.solver.algorithms import SearchAlgorithm
from frontend.shared.env import env_int
from frontend.shared.qt import QThread, Signal

_SOLVER_THREAD_STOP_TIMEOUT_MS = env_int(
    "FRONTEND_SOLVER_THREAD_STOP_TIMEOUT_MS", 250, minimum=1
)
_SOLVER_THREAD_FORCE_WAIT_MS = env_int(
    "FRONTEND_SOLVER_THREAD_FORCE_WAIT_MS", 500, minimum=1
)


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

    def stop(self, timeout_ms: int | None = None):
        """Stop the running worker thread.

        Args:
                timeout_ms: Optional override for graceful wait timeout.
        """
        timeout_ms = (
            _SOLVER_THREAD_STOP_TIMEOUT_MS
            if timeout_ms is None
            else max(1, int(timeout_ms))
        )
        self.requestInterruption()
        if not self.isRunning():
            self.state = None
            self.algo = None
            return

        # Give the worker an additional grace period before forcing termination.
        if not self.wait(timeout_ms):
            self.wait(_SOLVER_THREAD_FORCE_WAIT_MS)
            if self.isRunning():
                self.terminate()
                self.wait(_SOLVER_THREAD_FORCE_WAIT_MS)

        self.state = None
        self.algo = None

    def run(self):
        """Execute solver and emit either path or formatted error message."""
        try:
            if (
                self.isInterruptionRequested()
                or self.state is None
                or self.algo is None
            ):
                return
            solver = SearchAlgorithm(
                self.state, should_cancel=self.isInterruptionRequested
            )
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
