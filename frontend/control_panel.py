from frontend.shared.qt import QHBoxLayout, QLabel, QPushButton, QWidget, Signal, QMenu, QAction


SOLVER_ALGORITHMS = ("BFS", "DFS", "UCS", "A*")


class ControlPanel(QWidget):
	new_game_requested = Signal()
	restart_requested = Signal()
	undo_requested = Signal()
	hint_requested = Signal()
	solve_requested = Signal(str, str)
	auto_foundation_requested = Signal()

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setObjectName("ControlPanel")
		self._move_count_label = QLabel("Moves: 0")
		self._move_count_label.setObjectName("MoveCountLabel")
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
		layout = QHBoxLayout(self)
		layout.setContentsMargins(10, 10, 10, 10)
		layout.setSpacing(8)

		new_game_button = QPushButton("New Game")
		new_game_button.clicked.connect(self.new_game_requested.emit)
		layout.addWidget(new_game_button)

		restart_button = QPushButton("Restart")
		restart_button.clicked.connect(self.restart_requested.emit)
		layout.addWidget(restart_button)

		undo_button = QPushButton("Undo")
		undo_button.clicked.connect(self.undo_requested.emit)
		layout.addWidget(undo_button)

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
		layout.addWidget(solver_button)
		auto_button = QPushButton("Auto Foundation")
		auto_button.clicked.connect(self.auto_foundation_requested.emit)
		layout.addWidget(auto_button)

		layout.addStretch(1)
		layout.addWidget(self._move_count_label)

	def set_move_count(self, count: int):
		self._move_count_label.setText(f"Moves: {count}")

