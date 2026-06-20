import os
import sys
from PyQt5.QtCore import QLibraryInfo
from PyQt5.QtWidgets import QApplication
from ui.main_ui import MainUI

if __name__ == "__main__":
    # OpenCV may point Qt at its own incompatible platform plugins when cv2 is
    # imported by the UI handlers. Use the plugins that belong to PyQt5.
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = QLibraryInfo.location(
        QLibraryInfo.PluginsPath
    )
    app = QApplication(sys.argv)
    ui = MainUI()
    ui.show()
    sys.exit(app.exec_())
