from frontend.qt_compat import QHBoxLayout, QLabel, QPushButton, QWidget, Signal


class ControlPanel(QWidget):
	new_game_requested = Signal()
	undo_requested = Signal()
	hint_requested = Signal()
	auto_foundation_requested = Signal()

	def __init__(self, parent=None):
		super().__init__(parent)
		self._move_count_label = QLabel("Moves: 0")
		self._move_count_label.setStyleSheet("color: white; font-weight: bold; font-size: 16px;")
		self._build_ui()
		
		self.setStyleSheet("""
			QPushButton {
				background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #27ae60, stop:1 #1e8449);
				color: white;
				border: 1px solid #145a32;
				border-radius: 6px;
				padding: 8px 16px;
				font-weight: bold;
				font-size: 14px;
				min-width: 80px;
			}
			QPushButton:hover {
				background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2ecc71, stop:1 #229954);
				border: 1px solid #1e8449;
			}
			QPushButton:pressed {
				background-color: #145a32;
				border: 1px solid #0b351c;
			}
		""")
	def _build_ui(self):
		layout = QHBoxLayout(self)
		layout.setContentsMargins(10, 10, 10, 10)
		layout.setSpacing(8)

		new_game_button = QPushButton("New Game")
		new_game_button.clicked.connect(self.new_game_requested.emit)
		layout.addWidget(new_game_button)

		undo_button = QPushButton("Undo")
		undo_button.clicked.connect(self.undo_requested.emit)
		layout.addWidget(undo_button)

		hint_button = QPushButton("Hint")
		hint_button.clicked.connect(self.hint_requested.emit)
		layout.addWidget(hint_button)

		auto_button = QPushButton("Auto Foundation")
		auto_button.clicked.connect(self.auto_foundation_requested.emit)
		layout.addWidget(auto_button)

		layout.addStretch(1)
		layout.addWidget(self._move_count_label)

	def set_move_count(self, count: int):
		self._move_count_label.setText(f"Moves: {count}")

