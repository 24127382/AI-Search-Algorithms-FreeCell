import sys
from frontend.board_widget import BoardWidget
from frontend.control_panel import ControlPanel
from frontend.qt_compat import QApplication, QMainWindow, QMessageBox, QVBoxLayout, QWidget, QT_API


class MainWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setWindowTitle(f"FreeCell - {QT_API}")
		self.resize(800, 600)

		self.board = BoardWidget()
		self.controls = ControlPanel()

		container = QWidget()
		container.setObjectName("MainContainer")
		container.setStyleSheet("""
			QWidget#MainContainer {
				background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #2a6639, stop:1 #173d22);
			}
			QStatusBar {
				color: #e0e0e0;
				background-color: #08170d;
				font-size: 13px;
				font-weight: bold;
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
		self.controls.auto_foundation_requested.connect(self.board.auto_to_foundation)

		self.board.status_changed.connect(self.statusBar().showMessage)
		self.board.move_count_changed.connect(self.controls.set_move_count)
		self.board.game_won.connect(self._on_game_won)

	def _on_game_won(self):
		QMessageBox.information(self, "Victory", "You have completed the FreeCell game!")


def main():
	app = QApplication(sys.argv)
	window = MainWindow()
	window.show()
	sys.exit(app.exec())