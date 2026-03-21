"""Top control bar for game actions and solver selection."""

from frontend.shared.qt import QGridLayout, QLabel, QPushButton, QWidget, Signal, QMenu, QAction, Qt


SOLVER_ALGORITHMS = ("BFS", "DFS", "UCS", "A*")


class ControlPanel(QWidget):
	"""Action toolbar exposing game controls and solver mode choices."""

	new_game_requested = Signal()
	restart_requested = Signal()
	undo_requested = Signal()
	hint_requested = Signal()
	solve_requested = Signal(str, str)
	auto_foundation_requested = Signal()
	stop_solver_requested = Signal()

	def __init__(self, parent=None):
		"""Create controls, move counter, and style definitions.

		Args:
			parent: Optional parent widget.
		"""
		super().__init__(parent)
		self.setObjectName("ControlPanel")
		self._move_count_label = QLabel("Moves: 0")
		self._move_count_label.setObjectName("MoveCountLabel")
		self._stop_solver_button = None
		self._build_ui()
		
		self.setStyleSheet("""
			QWidget#ControlPanel {
				background-color: rgba(7, 24, 16, 0.52);
				border: 1px solid rgba(255, 255, 255, 0.14);
				border-radius: 10px;
			}
			QLabel#MoveCountLabel {
				color: #f4f8f5;
				font-weight: bold;
				font-size: 15pt;
				padding: 2px 8px;
				background-color: rgba(255, 255, 255, 0.08);
				border: 1px solid rgba(255, 255, 255, 0.2);
				border-radius: 8px;
			}
			QPushButton {
				background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2cb76a, stop:1 #1f8e51);
				color: white;
				border: 1px solid #145835;
				border-radius: 8px;
				padding: 8px 14px;
				font-weight: bold;
				font-size: 12pt;
				min-width: 92px;
			}
			QPushButton:hover {
				background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #36cc77, stop:1 #2a9f5c);
				border: 1px solid #1f874d;
			}
			QPushButton:pressed {
				background-color: #15653a;
				border: 1px solid #0e3d24;
			}
			QPushButton#StopSolverButton {
				background-color: rgba(255, 255, 255, 0.10);
				color: rgba(255, 255, 255, 0.92);
				border: 1px solid rgba(255, 255, 255, 0.34);
				border-radius: 7px;
				padding: 4px 10px;
				font-size: 10pt;
				font-weight: 600;
				min-width: 64px;
				max-width: 82px;
			}
			QPushButton#StopSolverButton:hover {
				background-color: rgba(255, 255, 255, 0.16);
				border: 1px solid rgba(255, 255, 255, 0.48);
			}
			QPushButton#StopSolverButton:pressed {
				background-color: rgba(255, 255, 255, 0.22);
				border: 1px solid rgba(255, 255, 255, 0.56);
			}
			QMenu {
				background-color: #123a24;
				color: #f2fbf4;
				border: 1px solid #1f6d43;
				padding: 6px;
			}
			QMenu::item {
				padding: 7px 16px;
				border-radius: 6px;
			}
			QMenu::item:selected {
				background-color: #219358;
			}
		""")
	def _build_ui(self):
		"""Build buttons and nested solver menu, then wire signals."""
		layout = QGridLayout(self)
		layout.setContentsMargins(10, 10, 10, 8)
		layout.setHorizontalSpacing(8)
		layout.setVerticalSpacing(6)

		new_game_button = QPushButton("New Game")
		new_game_button.clicked.connect(self.new_game_requested.emit)
		layout.addWidget(new_game_button, 0, 0)

		restart_button = QPushButton("Restart")
		restart_button.clicked.connect(self.restart_requested.emit)
		layout.addWidget(restart_button, 0, 1)

		undo_button = QPushButton("Undo")
		undo_button.clicked.connect(self.undo_requested.emit)
		layout.addWidget(undo_button, 0, 2)

		solver_button = QPushButton("Solver")
		solver_menu = QMenu(solver_button)
		for algo in SOLVER_ALGORITHMS:
			if algo != "UCS":
				action = QAction(algo, self)
				action.triggered.connect(lambda checked, a=algo: self.solve_requested.emit(a, "speed"))
				solver_menu.addAction(action)
				continue

			ucs_menu = QMenu("UCS", solver_menu)

			ucs_first_action = QAction("First Solution", self)
			ucs_first_action.triggered.connect(lambda checked: self.solve_requested.emit("UCS", "first"))
			ucs_menu.addAction(ucs_first_action)

			ucs_speed_action = QAction("Speed + Cost", self)
			ucs_speed_action.triggered.connect(lambda checked: self.solve_requested.emit("UCS", "speed"))
			ucs_menu.addAction(ucs_speed_action)

			ucs_memory_action = QAction("Exact Memory", self)
			ucs_memory_action.triggered.connect(lambda checked: self.solve_requested.emit("UCS", "memory"))
			ucs_menu.addAction(ucs_memory_action)

			solver_menu.addMenu(ucs_menu)
		solver_button.setMenu(solver_menu)
		layout.addWidget(solver_button, 0, 3, Qt.AlignmentFlag.AlignHCenter)

		auto_button = QPushButton("Auto Foundation")
		auto_button.clicked.connect(self.auto_foundation_requested.emit)
		layout.addWidget(auto_button, 0, 4)

		layout.setColumnStretch(5, 1)
		layout.addWidget(self._move_count_label, 0, 6)

		self._stop_solver_button = QPushButton("Stop")
		self._stop_solver_button.setObjectName("StopSolverButton")
		stop_button_size_policy = self._stop_solver_button.sizePolicy()
		stop_button_size_policy.setRetainSizeWhenHidden(True)
		self._stop_solver_button.setSizePolicy(stop_button_size_policy)
		self._stop_solver_button.setVisible(False)
		self._stop_solver_button.clicked.connect(self.stop_solver_requested.emit)
		layout.addWidget(self._stop_solver_button, 1, 3, Qt.AlignmentFlag.AlignHCenter)

	def set_move_count(self, count: int):
		"""Update move counter label.

		Args:
			count: Current number of performed moves.
		"""
		self._move_count_label.setText(f"Moves: {count}")

	def set_solver_running(self, is_running: bool):
		"""Toggle visibility of the solver stop button.

		Args:
			is_running: Whether a solver worker thread is currently running.
		"""
		if self._stop_solver_button is None:
			return
		self._stop_solver_button.setVisible(is_running)

