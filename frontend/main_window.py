"""Main application window and deal-number startup dialog."""

from frontend.board.widget import BoardWidget
from frontend.control_panel import ControlPanel
from frontend.shared.qt import QDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QVBoxLayout, QWidget, QT_API


class DealNumberDialog(QDialog):
	"""Modal dialog that lets the player input an optional deal number."""

	def __init__(self, parent=None, initial_deal_number: int | None = None):
		"""Initialize dialog defaults and build input controls.

		Args:
			parent: Optional parent widget.
			initial_deal_number: Optional value to prefill input.
		"""
		super().__init__(parent)
		self.selected_deal_number: int | None = initial_deal_number
		self.setWindowTitle("Start Game")
		self.setModal(True)
		self.resize(460, 200)
		self.setStyleSheet("""
			QDialog {
				background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #153824, stop:1 #0d2517);
			}
			QLabel {
				color: #eff9f1;
			}
			QPushButton {
				background-color: #1f8f52;
				color: white;
				border: 1px solid #15663a;
				border-radius: 8px;
				padding: 8px 14px;
				font-weight: bold;
				font-size: 11pt;
			}
			QPushButton:hover {
				background-color: #27a85f;
			}
			QPushButton:pressed {
				background-color: #187843;
			}
			QLineEdit {
				background-color: rgba(255, 255, 255, 0.92);
				color: #111111;
				border: 1px solid #15663a;
				border-radius: 8px;
				padding: 8px 10px;
				font-size: 11pt;
			}
		""")
		self._build_ui()

	def _build_ui(self):
		"""Construct title, deal input, and start button."""
		layout = QVBoxLayout(self)
		layout.setContentsMargins(18, 16, 18, 16)
		layout.setSpacing(12)

		title = QLabel("Enter a Deal Number or leave empty for random")
		title.setStyleSheet("font-size: 13pt; font-weight: bold;")
		layout.addWidget(title)

		self._deal_input = QLineEdit()
		self._deal_input.setPlaceholderText("Example: 1, -42, 999999999")
		if self.selected_deal_number is not None:
			self._deal_input.setText(str(self.selected_deal_number))
		layout.addWidget(self._deal_input)

		button_row = QHBoxLayout()
		button_row.setSpacing(8)
		start_button = QPushButton("Start")
		start_button.clicked.connect(self._confirm)
		cancel_button = QPushButton("Cancel")
		cancel_button.clicked.connect(self.reject)
		button_row.addWidget(start_button)
		button_row.addWidget(cancel_button)
		layout.addLayout(button_row)

	def _confirm(self):
		"""Validate optional deal input and close dialog.

		"""
		raw_value = self._deal_input.text().strip()
		if not raw_value:
			self.selected_deal_number = None
			self.accept()
			return

		try:
			deal_number = int(raw_value)
		except ValueError:
			QMessageBox.warning(self, "Invalid Deal Number", "Deal number must be a valid integer.")
			return

		self.selected_deal_number = deal_number
		self.accept()


class VictoryDialog(QDialog):
	"""Dialog shown after winning with quick next actions."""

	def __init__(self, parent=None):
		super().__init__(parent)
		self.selected_action: str | None = None
		self.setWindowTitle("Victory")
		self.setModal(True)
		self.resize(460, 210)
		self.setStyleSheet("""
			QDialog {
				background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #153824, stop:1 #0d2517);
			}
			QLabel {
				color: #eff9f1;
			}
			QPushButton {
				background-color: #1f8f52;
				color: white;
				border: 1px solid #15663a;
				border-radius: 8px;
				padding: 8px 14px;
				font-weight: bold;
				font-size: 11pt;
			}
			QPushButton:hover {
				background-color: #27a85f;
			}
			QPushButton:pressed {
				background-color: #187843;
			}
		""")
		self._build_ui()

	def _build_ui(self):
		layout = QVBoxLayout(self)
		layout.setContentsMargins(18, 16, 18, 16)
		layout.setSpacing(12)

		title = QLabel("Congratulations! You won FreeCell.")
		title.setStyleSheet("font-size: 13pt; font-weight: bold;")
		layout.addWidget(title)

		subtitle = QLabel("Choose your next action:")
		subtitle.setStyleSheet("font-size: 10.5pt;")
		layout.addWidget(subtitle)

		button_row = QHBoxLayout()
		button_row.setSpacing(8)

		new_game_button = QPushButton("New Game")
		new_game_button.clicked.connect(self._choose_new_game)
		back_button = QPushButton("Back to previous game")
		back_button.clicked.connect(self._choose_back)

		button_row.addWidget(new_game_button)
		button_row.addWidget(back_button)
		layout.addLayout(button_row)

	def _choose_new_game(self):
		self.selected_action = "new_game"
		self.accept()

	def _choose_back(self):
		self.selected_action = "back_previous"
		self.accept()


class MainWindow(QMainWindow):
	"""Top-level container that hosts controls and the game board."""

	def __init__(self, deal_number: int | None = None):
		"""Create main window with initialized board and control panel.

		Args:
			deal_number: Optional fixed deal number for board setup.
		"""
		super().__init__()
		self.selected_deal_number: int | None = deal_number
		self.current_deal_number: int | None = None
		self.setWindowTitle(f"FreeCell - {QT_API}")
		self.resize(1000, 750)

		self.board = BoardWidget(deal_number=deal_number)
		self.controls = ControlPanel()

		container = QWidget()
		container.setObjectName("MainContainer")
		container.setStyleSheet("""
			QWidget#MainContainer {
				background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #2d7341, stop:0.55 #1b4c2d, stop:1 #102d1c);
			}
			QStatusBar {
				color: #eef8f1;
				background-color: rgba(6, 16, 10, 0.86);
				font-size: 12pt;
				font-weight: bold;
				border-top: 1px solid rgba(255, 255, 255, 0.15);
			}
		""")
		layout = QVBoxLayout(container)
		layout.setContentsMargins(8, 8, 8, 8)
		layout.setSpacing(6)
		layout.addWidget(self.controls)
		layout.addWidget(self.board)
		self.setCentralWidget(container)

		self._connect_signals()
		if self.board.current_deal_number is not None:
			self._on_deal_number_changed(self.board.current_deal_number)
		self.statusBar().showMessage(f"Ready - Deal #{self.board.current_deal_number}.")

	def _connect_signals(self):
		"""Wire control actions to board operations and status updates."""
		self.controls.new_game_requested.connect(self._on_new_game_requested)
		self.controls.restart_requested.connect(self.board.restart)
		self.controls.undo_requested.connect(self.board.undo)
		self.controls.solve_requested.connect(self.board.solve_with_algo)
		self.controls.auto_foundation_requested.connect(self.board.auto_to_foundation)
		self.controls.stop_solver_requested.connect(self.board.stop_solver)

		self.board.status_changed.connect(self.statusBar().showMessage)
		self.board.move_count_changed.connect(self.controls.set_move_count)
		self.board.deal_number_changed.connect(self._on_deal_number_changed)
		self.board.solver_running_changed.connect(self.controls.set_solver_running)
		self.board.game_won.connect(self._on_game_won)

	def _on_deal_number_changed(self, deal_number: int):
		"""Persist and display current deal number in main window metadata."""
		self.current_deal_number = deal_number
		self.setWindowTitle(f"FreeCell - {QT_API} - Deal #{deal_number}")

	def _on_new_game_requested(self):
		"""Prompt optional deal number and start a new game from that input."""
		dialog = DealNumberDialog(self, initial_deal_number=self.current_deal_number)
		if dialog.exec() != QDialog.DialogCode.Accepted:
			return

		self.board.requested_deal_number = dialog.selected_deal_number
		try:
			self.board.new_game()
		except ValueError as exc:
			QMessageBox.warning(self, "Cannot Start Deal", str(exc))

	def _on_game_won(self):
		"""Display a victory dialog with follow-up actions after winning."""
		dialog = VictoryDialog(self)
		if dialog.exec() != QDialog.DialogCode.Accepted:
			return

		if dialog.selected_action == "new_game":
			self._on_new_game_requested()
			return

		if dialog.selected_action == "back_previous":
			if not self.board.restore_previous_game_state():
				QMessageBox.information(self, "No Previous Game", "No previous game state is available to restore.")