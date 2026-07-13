import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import VideoRenamerGUI

def main():
    app = QApplication(sys.argv)
    window = VideoRenamerGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
