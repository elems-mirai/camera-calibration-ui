import os
import sys
import re
from PyQt5.QtWidgets import (
    QDialog,
    QApplication,
    QButtonGroup,
    QFileDialog,
    QPushButton,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSizePolicy,
    QSplitter,
)
from PyQt5.uic import loadUi
from PyQt5.QtCore import QStringListModel, Qt, QRect

from ui.clickable_label import ClickableLabel
from ui.tab1_handler import Tab1Handler
from ui.tab2_handler import Tab2Handler

import os
os.environ["QT_LOGGING_RULES"] = "qt.qpa.wayland.warning=false"

class MainUI(QDialog):
    def __init__(self):
        super(MainUI, self).__init__()
        loadUi("resources/main.ui", self)
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowTitleHint
            | Qt.WindowSystemMenuHint
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )
        self.setWindowModality(Qt.NonModal)
        self.setSizeGripEnabled(True)
        self.setMaximumSize(16777215, 16777215)
        self._ui_scale = 1.0
        self._cancel_requested = False
        self._shutting_down = False

        # --- Tab1 display with ClickableLabel ---
        self._display_target_tab1 = ClickableLabel(self.tab)
        self.style_camWin = self.cameraWindow.styleSheet()
        self._display_target_tab1.setGeometry(self.cameraWindow.geometry())
        self._display_target_tab1.setObjectName("cameraWindow")
        self._display_target_tab1.setStyleSheet(self.style_camWin)
        self._display_target_tab1.show()
        self.cameraWindow.setParent(None)

        # --- Tab2 display with ClickableLabel ---
        self._display_target_tab2 = ClickableLabel(self.tab_2)
        self.style_camWin_3 = self.cameraWindow_3.styleSheet()
        self._display_target_tab2.setGeometry(self.cameraWindow_3.geometry())
        self._display_target_tab2.setObjectName("cameraWindow_3")
        self._display_target_tab2.setStyleSheet(self.style_camWin_3)
        self._display_target_tab2.show()
        self.cameraWindow_3.setParent(None)

        # --- QListView models ---
        self.list_model = QStringListModel()
        self.imageList.setModel(self.list_model)
        self.list_model_tab2 = QStringListModel()
        self.imageList_3.setModel(self.list_model_tab2)

        self.width = 1920
        self.height = 1080
        self.frame_rate = 15
        self._setup_checkerboard_sizes()
        self._hide_resolution_controls()

        # --- Folder-only workflow controls ---
        self.Open_folder_tab1 = QPushButton("Open Folder", self.tab)
        self.Open_folder_tab1.setGeometry(self._scaled_rect(20, 430, 211, 51))
        self.Open_folder_tab1.show()

        self.Open_folder = QPushButton("Open Folder", self.tab_2)
        self.Open_folder.setGeometry(self._scaled_rect(2240, 1090, 201, 51))
        self.Open_folder.show()
        self.Calculate_points.setParent(None)
        self._create_p6_controls()
        self._build_responsive_layout()

        # --- Handlers ---
        self.tab1 = Tab1Handler(self)
        self.tab2 = Tab2Handler(self)

        self.tabWidget.currentChanged.connect(self.on_tab_changed)

        # --- Tab1 connections ---
        self.imageList.clicked.connect(self.tab1.show_selected_image_index)
        self.AvailableCams_tab1.currentIndexChanged.connect(self.tab1.on_camera_changed)
        self.CameraView_tab1.clicked.connect(self.tab1.open_camera)
        self.Open_folder_tab1.clicked.connect(self.tab1.open_folder)

        self.Take_a_Pic_tab1.clicked.connect(self.tab1.take_picture)
        self.DeleteImage_tab1.clicked.connect(self.tab1.delete_selected_image)
        self.IntrinsicCalibrate.clicked.connect(self.tab1.intrinsic_calibrate)
        
        # --- Tab2 connections ---
        self.AvailableCams.currentIndexChanged.connect(self.tab2.on_camera_changed)
        self.CameraView.clicked.connect(self.tab2.open_camera)
        self.Take_a_Pic.clicked.connect(self.tab2.take_picture)
        self.ClearPoints.clicked.connect(self.tab2.clear_points_button)
        self.DeleteImage.clicked.connect(self.tab2.delete_selected_image)
        self.Open_folder.clicked.connect(self.tab2.open_folder)
        self.imageList_3.clicked.connect(self.tab2.show_selected_image_index)
        self.ExtrinsicCalibrate.clicked.connect(self.tab2.run_extrinsic_calibration)

    def _setup_checkerboard_sizes(self):
        sizes = ["10x7", "11x8", "9x6", "7x4", "6x3", "6x9", "8x6", "7x5", "10x4"]
        current = self.CheckerBoardSizeBox.currentText().strip()
        if current and current not in sizes:
            sizes.insert(0, current)

        self.CheckerBoardSizeBox.clear()
        self.CheckerBoardSizeBox.addItems(sizes)
        self.CheckerBoardSizeBox.setEditable(True)
        self.CheckerBoardSizeBox.setCurrentText(current or sizes[0])

    def _hide_resolution_controls(self):
        self.CameraDemBox_tab1.hide()
        self.CameraDemBox.hide()

    def _build_responsive_layout(self):
        self.setWindowTitle("Camera Calibration")
        self.setMinimumSize(940, 560)
        self.setMaximumSize(16777215, 16777215)
        self.tab.setObjectName("main_panel")
        self.tab_2.setObjectName("main_panel")
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(min(1280, available.width() - 40), min(820, available.height() - 80))
        else:
            self.resize(1280, 820)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.addWidget(self.tabWidget)

        tab1_index = self.tabWidget.indexOf(self.tab)
        tab2_index = self.tabWidget.indexOf(self.tab_2)
        self.tabWidget.setTabText(tab1_index, "Intrinsic")
        self.tabWidget.setTabText(tab2_index, "Extrinsic")
        self.tabWidget.setTabToolTip(tab1_index, "Intrinsic Calibration")
        self.tabWidget.setTabToolTip(tab2_index, "Extrinsic Calibration")

        self._style_controls()
        self._build_tab1_layout()
        self._build_tab2_layout()

    def _style_controls(self):
        for widget in self.findChildren(QWidget):
            widget.setStyleSheet("")

        self.setStyleSheet(
            """
            QDialog {
                background-color: #ececec;
                color: #222222;
            }
            QWidget#main_panel {
                background-color: #ececec;
                border: none;
            }
            QWidget, QLabel, QRadioButton, QComboBox, QPushButton, QLineEdit, QListView {
                font-family: "Segoe UI", "Ubuntu", "Arial", sans-serif;
                font-size: 12px;
                color: #222222;
            }
            QTabWidget::pane {
                border: 1px solid #bcbcbc;
                background-color: #ececec;
            }
            QTabBar::tab {
                background: #dcdcdc;
                border: 1px solid #bcbcbc;
                padding: 6px 12px;
                min-width: 92px;
                font-size: 12px;
                font-weight: 600;
                color: #444444;
            }
            QTabBar::tab:selected {
                background: #ececec;
                border-bottom-color: #ececec;
                color: #000000;
            }
            QGroupBox {
                border: 1px solid #c4c4c4;
                border-radius: 2px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: 600;
                background: transparent;
            }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 8px; padding: 0 4px; }
            QLabel { font-weight: normal; }
            QPushButton {
                min-height: 24px;
                padding: 4px 8px;
                border: 1px solid #aaaaaa;
                background: #e0e0e0;
                border-radius: 2px;
                color: #111111;
            }
            QPushButton:hover { background: #d0d0d0; }
            QPushButton:pressed { background: #c0c0c0; }
            QComboBox, QLineEdit {
                min-height: 24px;
                background: #ffffff;
                border: 1px solid #a0a0a0;
                padding: 3px;
                color: #000000;
            }
            QListView {
                border: 1px solid #a0a0a0;
                background: #ffffff;
            }
            """
        )
        for button in [
            self.IntrinsicCalibrate,
            self.ExtrinsicCalibrate,
            self.Take_a_Pic_tab1,
            self.Take_a_Pic,
        ]:
            button.setStyleSheet("background: #005a9e; color: white; border: 1px solid #004b85; font-weight: 600;")
        self.DeleteImage_tab1.setStyleSheet("background: #fdf2f2; color: #a80000; border: 1px solid #d83b01;")
        self.DeleteImage.setStyleSheet("background: #fdf2f2; color: #a80000; border: 1px solid #d83b01;")
        self.ClearPoints.setStyleSheet("")

    def _style_preview(self, widget):
        widget.setStyleSheet(
            "border: 1px solid #c8ccd2;"
            "border-radius: 2px;"
            "background-color: #f6f7f8;"
            "color: #8a929c;"
            "font-size: 14px;"
            "font-weight: 500;"
        )
        widget.setAlignment(Qt.AlignCenter)
        widget.setText("No image loaded")

    def _create_p6_controls(self):
        if hasattr(self, "imgPnt6"):
            return
        self.imgPnt6 = QRadioButton("P6", self.tab_2)
        self.ImgPnt6X = QLineEdit(self.tab_2)
        self.ImgPnt6Y = QLineEdit(self.tab_2)
        self.WrldPnt6X = QLineEdit(self.tab_2)
        self.WrldPnt6Y = QLineEdit(self.tab_2)
        self.ImgPnt6X.setReadOnly(True)
        self.ImgPnt6Y.setReadOnly(True)
        for field in [self.ImgPnt6X, self.ImgPnt6Y, self.WrldPnt6X, self.WrldPnt6Y]:
            field.setMinimumWidth(85)

    def _build_tab1_layout(self):
        self.label_24.setText("Camera Source")
        self.CheckerBoardSize.setText("Checkerboard inner corners")
        self.Source.setText("Intrinsic Images")

        camera_group = QGroupBox("Camera Configuration")
        camera_layout = QVBoxLayout(camera_group)
        camera_layout.setSpacing(6)
        for widget in [
            self.label_24,
            self.AvailableCams_tab1,
            self.Open_folder_tab1,
        ]:
            camera_layout.addWidget(widget)

        capture_group = QGroupBox("Capture")
        capture_layout = QVBoxLayout(capture_group)
        capture_layout.setSpacing(6)
        for widget in [
            self.CameraView_tab1,
            self.Take_a_Pic_tab1,
        ]:
            capture_layout.addWidget(widget)

        calibration_group = QGroupBox("Intrinsic Calibration")
        calibration_layout = QVBoxLayout(calibration_group)
        calibration_layout.setSpacing(6)
        for widget in [
            self.CheckerBoardSize,
            self.CheckerBoardSizeBox,
            self.IntrinsicCalibrate,
        ]:
            calibration_layout.addWidget(widget)

        image_group = QGroupBox("Intrinsic Images")
        image_layout = QVBoxLayout(image_group)
        image_layout.setSpacing(6)
        image_layout.addWidget(self.Source)
        image_layout.addWidget(self.imageList)
        image_layout.addWidget(self.DeleteImage_tab1)

        left_panel = QWidget()
        left_panel.setObjectName("main_panel")
        left_panel.setFixedWidth(240)
        controls = QVBoxLayout(left_panel)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)
        for widget in [
            camera_group,
            capture_group,
            calibration_group,
            image_group,
        ]:
            controls.addWidget(widget)
        controls.setStretch(3, 1)

        self._display_target_tab1.setMinimumSize(520, 320)
        self._display_target_tab1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._style_preview(self._display_target_tab1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(self._display_target_tab1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 950])

        layout = QHBoxLayout(self.tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(splitter)

    def _build_tab2_layout(self):
        self.label_23.setText("Camera Source")
        self.label.setText("Extrinsic Images")

        camera_group = QGroupBox("Camera Configuration")
        camera_layout = QVBoxLayout(camera_group)
        camera_layout.setSpacing(6)
        for widget in [
            self.label_23,
            self.AvailableCams,
            self.Open_folder,
        ]:
            camera_layout.addWidget(widget)

        capture_group = QGroupBox("Capture")
        capture_layout = QVBoxLayout(capture_group)
        capture_layout.setSpacing(6)
        for widget in [
            self.CameraView,
            self.Take_a_Pic,
        ]:
            capture_layout.addWidget(widget)

        calibration_group = QGroupBox("Extrinsic Calibration")
        calibration_layout = QVBoxLayout(calibration_group)
        calibration_layout.setSpacing(6)
        for widget in [
            self.ClearPoints,
            self.ExtrinsicCalibrate,
        ]:
            calibration_layout.addWidget(widget)

        image_group = QGroupBox("Extrinsic Images")
        image_layout = QVBoxLayout(image_group)
        image_layout.setSpacing(6)
        image_layout.addWidget(self.label)
        image_layout.addWidget(self.imageList_3)
        image_layout.addWidget(self.DeleteImage)

        left_panel = QWidget()
        left_panel.setObjectName("main_panel")
        left_panel.setFixedWidth(240)
        controls = QVBoxLayout(left_panel)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)
        for widget in [
            camera_group,
            capture_group,
            calibration_group,
            image_group,
        ]:
            controls.addWidget(widget)
        controls.setStretch(3, 1)

        self._display_target_tab2.setMinimumSize(240, 320)
        self._display_target_tab2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._style_preview(self._display_target_tab2)

        for label in [
            self.label_3, self.label_4, self.label_6, self.label_8, self.label_10,
            self.label_11, self.label_12, self.label_13, self.label_14, self.label_15,
            self.label_16, self.label_17, self.label_18, self.label_19, self.label_20,
            self.label_21, self.label_22,
        ]:
            label.hide()

        right_widget = QWidget()
        right_widget.setObjectName("main_panel")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        point_group = QGroupBox("Ground Control Points (P1-P6)")
        point_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        point_layout = QVBoxLayout(point_group)
        point_layout.setContentsMargins(8, 12, 8, 8)
        point_layout.setSpacing(0)

        point_grid = QGridLayout()
        point_grid.setContentsMargins(0, 0, 0, 0)
        point_grid.setHorizontalSpacing(6)
        point_grid.setVerticalSpacing(5)

        headers = ["", "Point", "Image X", "Image Y", "World X", "World Y"]
        widths = [28, 42, 78, 78, 85, 85]
        for column, text in enumerate(headers):
            header = QLabel(text)
            header.setAlignment(Qt.AlignCenter)
            header.setFixedWidth(widths[column])
            header.setStyleSheet(
                "font-size: 10px;"
                "font-weight: 600;"
                "color: #444;"
                "padding: 2px 0;"
            )
            point_grid.addWidget(header, 0, column)

        self.point_button_group = QButtonGroup(self)
        self.point_button_group.setExclusive(True)

        for row in range(1, 7):
            radio_container = QWidget()
            radio_layout = QHBoxLayout(radio_container)
            radio_layout.setContentsMargins(0, 0, 0, 0)
            radio_layout.setAlignment(Qt.AlignCenter)
            radio = getattr(self, f"imgPnt{row}")
            radio.setText("")
            self.point_button_group.addButton(radio, row)
            radio_layout.addWidget(radio)
            radio_container.setFixedWidth(widths[0])
            point_grid.addWidget(radio_container, row, 0)

            point_label = QLabel(f"P{row}")
            point_label.setAlignment(Qt.AlignCenter)
            point_label.setFixedWidth(widths[1])
            point_label.setStyleSheet("font-weight: 600; color: #222;")
            point_grid.addWidget(point_label, row, 1)

            for column, field_name in [
                (2, f"ImgPnt{row}X"),
                (3, f"ImgPnt{row}Y"),
                (4, f"WrldPnt{row}X"),
                (5, f"WrldPnt{row}Y"),
            ]:
                field = getattr(self, field_name)
                field.setFixedWidth(widths[column])
                field.setFixedHeight(28)
                field.setAlignment(Qt.AlignCenter if column in (2, 3) else Qt.AlignLeft | Qt.AlignVCenter)
                if column in (2, 3):
                    field.setReadOnly(True)
                    field.setPlaceholderText("-")
                    field.setStyleSheet(
                        "background-color: #f2f2f2; color: #555555; "
                        "border: 1px solid #d0d4da; padding: 2px;"
                    )
                else:
                    field.setPlaceholderText("0.000")
                    field.setStyleSheet(
                        "background-color: #ffffff; color: #000000; "
                        "border: 1px solid #b5b5b5; padding: 2px;"
                    )
                point_grid.addWidget(field, row, column)

        point_layout.addLayout(point_grid)
        right_layout.addWidget(point_group)
        right_layout.addStretch(1)
        right_widget.setFixedWidth(438)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(self._display_target_tab2)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([240, 600, 438])

        layout = QHBoxLayout(self.tab_2)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(splitter)

    def _apply_screen_scale(self):
        """Scale the fixed Qt Designer geometry to the current display."""
        screen = QApplication.primaryScreen()
        if screen is None:
            self._ui_scale = 1.0
            return

        available = screen.availableGeometry()
        design = self.geometry()
        margin_w = 40
        margin_h = 80
        scale_w = max(0.1, (available.width() - margin_w) / design.width())
        scale_h = max(0.1, (available.height() - margin_h) / design.height())
        self._ui_scale = min(1.0, scale_w, scale_h)

        if self._ui_scale >= 0.999:
            return

        for widget in self.findChildren(QWidget):
            geom = widget.geometry()
            if geom.isValid():
                widget.setGeometry(self._scale_qrect(geom))
            style = widget.styleSheet()
            if style:
                widget.setStyleSheet(self._scaled_stylesheet(style))

        self.resize(
            int(design.width() * self._ui_scale),
            int(design.height() * self._ui_scale),
        )
        self.move(
            available.x() + max(0, (available.width() - self.width()) // 2),
            available.y() + max(0, (available.height() - self.height()) // 2),
        )
        print(f"[MainUI] UI scaled to {self._ui_scale:.2f} for current display")

    def _scale_qrect(self, rect):
        return QRect(
            int(rect.x() * self._ui_scale),
            int(rect.y() * self._ui_scale),
            max(1, int(rect.width() * self._ui_scale)),
            max(1, int(rect.height() * self._ui_scale)),
        )

    def _scaled_rect(self, x, y, w, h):
        return QRect(
            int(x * self._ui_scale),
            int(y * self._ui_scale),
            max(1, int(w * self._ui_scale)),
            max(1, int(h * self._ui_scale)),
        )

    def _scaled_stylesheet(self, style):
        def scale_font(match):
            size = float(match.group(1))
            scaled = max(8.0, size * self._ui_scale)
            if scaled.is_integer():
                return f"font-size: {int(scaled)}pt"
            return f"font-size: {scaled:.1f}pt"

        return re.sub(r"font-size:\s*(\d+(?:\.\d+)?)pt", scale_font, style)

    # --------------------------------------------
    # Tab switching behavior
    # --------------------------------------------
    def on_tab_changed(self, index):
        """Handle tab switching: enable only the active tab's ClickableLabel"""

        tab1_index = self.tabWidget.indexOf(self.tab)
        tab2_index = self.tabWidget.indexOf(self.tab_2)

        self._display_target_tab1.setEnabled(index == tab1_index)
        self._display_target_tab2.setEnabled(index == tab2_index)
        self._display_target_tab1.setVisible(index == tab1_index)
        self._display_target_tab2.setVisible(index == tab2_index)

        self.tab1.on_tab_changed(index)
        self.tab2.on_tab_changed(index)

        print(f"[MainUI] Active tab changed to {index}")

    # --------------------------------------------
    # Prevent ESC key from closing the window
    # --------------------------------------------
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            event.ignore()
        else:
            super().keyPressEvent(event)

    def request_cancel(self):
        self._cancel_requested = True

    def clear_cancel_request(self):
        if not self._shutting_down:
            self._cancel_requested = False

    def should_cancel(self):
        return self._cancel_requested or self._shutting_down

    def shutdown(self):
        if self._shutting_down:
            return
        self._cancel_requested = True
        self._shutting_down = True

        for handler in (getattr(self, "tab1", None), getattr(self, "tab2", None)):
            if handler is None:
                continue
            try:
                if handler.timer.isActive():
                    handler.timer.stop()
                if handler.cap:
                    handler.cap.release()
                    handler.cap = None
            except Exception as error:
                print(f"[MainUI] Camera cleanup error: {error}")

        print("[MainUI] Shutdown complete")

    def closeEvent(self, event):
        self.request_cancel()
        self.shutdown()
        event.accept()
