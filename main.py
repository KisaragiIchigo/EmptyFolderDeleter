import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
import gui

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("メイリオ", 10))

    win = gui.MainWindow()
    win.show()
    sys.exit(app.exec())
