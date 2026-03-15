import sys
from frontend.board_widget import BoardWidget
from frontend.control_panel import ControlPanel
from frontend.qt_compat import QApplication, QDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QVBoxLayout, QWidget, QT_API


class DifficultyDialog(QDialog):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.selected_difficulty = "medium"
		self.setWindowTitle("Choose Difficulty")
		self.setModal(True)
		self.resize(430, 160)
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

		title = QLabel("Chọn cấp độ trước khi vào game")
		title.setStyleSheet("font-size: 13pt; font-weight: bold;")
		layout.addWidget(title)

		button_row = QHBoxLayout()
		button_row.setSpacing(8)
		for level in ("easy", "medium", "hard", "expert"):
			button = QPushButton(level.title())
			button.clicked.connect(lambda _, lv=level: self._choose_level(lv))
			button_row.addWidget(button)
		layout.addLayout(button_row)

	def _choose_level(self, level: str):
		self.selected_difficulty = level
		self.accept()


class MainWindow(QMainWindow):
	def __init__(self, difficulty: str = "medium"):
		super().__init__()
		self.setWindowTitle(f"FreeCell - {QT_API}")
		self.resize(800, 600)

		self.board = BoardWidget(difficulty=difficulty)
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
		self.statusBar().showMessage("Ready.")

	def _connect_signals(self):
		self.controls.new_game_requested.connect(self.board.new_game)
		self.controls.undo_requested.connect(self.board.undo)
		self.controls.hint_requested.connect(self.board.hint)
		self.controls.solve_requested.connect(self.board.solve_with_algo)
		self.controls.auto_foundation_requested.connect(self.board.auto_to_foundation)

		self.board.status_changed.connect(self.statusBar().showMessage)
		self.board.move_count_changed.connect(self.controls.set_move_count)
		self.board.game_won.connect(self._on_game_won)

	def _on_game_won(self):
		QMessageBox.information(self, "Victory", "You have completed the FreeCell game!")


def main():
	app = QApplication(sys.argv)
	difficulty_dialog = DifficultyDialog()
	if difficulty_dialog.exec() != QDialog.DialogCode.Accepted:
		sys.exit(0)

	window = MainWindow(difficulty=difficulty_dialog.selected_difficulty)
	window.show()
	sys.exit(app.exec())