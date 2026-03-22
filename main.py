import sys
from frontend.main_window import DealNumberDialog, MainWindow
from frontend.shared.qt import QApplication, QDialog


def main():
	"""Run Qt application after user provides optional deal number.

	Returns:
		None: This function exits via `sys.exit`.
	"""
	app = QApplication(sys.argv)
	deal_dialog = DealNumberDialog()
	if deal_dialog.exec() != QDialog.DialogCode.Accepted:
		sys.exit(0)

	window = MainWindow(deal_number=deal_dialog.selected_deal_number)
	window.show()
	sys.exit(app.exec())


if __name__ == "__main__":
    main()