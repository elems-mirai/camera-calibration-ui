import os
import signal
import sys
from PyQt5.QtCore import QLibraryInfo, QTimer
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
    app.aboutToQuit.connect(ui.shutdown)

    def stop_app(*_):
        print("\n[Main] Stop requested")
        ui.close()
        app.quit()

    signal.signal(signal.SIGINT, stop_app)

    # Let Python process Ctrl+C while the Qt event loop is active.
    interrupt_timer = QTimer()
    interrupt_timer.timeout.connect(lambda: None)
    interrupt_timer.start(200)

    ui.show()
    sys.exit(app.exec_())
