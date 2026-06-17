from __future__ import annotations

import os
import sys

from PyQt5.QtWidgets import QApplication

if __package__ in {None, ""}:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from calibration_val.window import ValidationWindow
else:
    from .window import ValidationWindow


def main() -> int:
    os.environ["QT_LOGGING_RULES"] = "qt.qpa.wayland.warning=false"
    app = QApplication(sys.argv)
    window = ValidationWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
