import sys
from PyQt5.QtWidgets import QApplication
from ui.main_ui import MainUI

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = MainUI()
    ui.show()
    sys.exit(app.exec_())
