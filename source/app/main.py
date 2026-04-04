import os
import sys

os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg=false")

from source.presentation.qt.main_window import DealNumberDialog, MainWindow
from source.presentation.qt.shared.qt import QApplication, QDialog


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
