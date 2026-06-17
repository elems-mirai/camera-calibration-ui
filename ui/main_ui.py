import os
import sys
from PyQt5.QtWidgets import QDialog, QApplication, QFileDialog, QPushButton
from PyQt5.uic import loadUi
from PyQt5.QtCore import QStringListModel, Qt   # ✅ Add Qt here

from ui.clickable_label import ClickableLabel
from ui.tab1_handler import Tab1Handler
from ui.tab2_handler import Tab2Handler

import os
os.environ["QT_LOGGING_RULES"] = "qt.qpa.wayland.warning=false"

class MainUI(QDialog):
    def __init__(self):
        super(MainUI, self).__init__()
        loadUi("resources/main.ui", self)

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

        self.width = 1920
        self.height = 1080
        self.frame_rate = 8

        # --- Handlers ---
        self.tab1 = Tab1Handler(self)
        self.tab2 = Tab2Handler(self)

        # --- Folder-only workflow controls ---
        self.Open_folder_tab1 = QPushButton("Open Folder", self.tab)
        self.Open_folder_tab1.setGeometry(20, 430, 211, 51)
        self.Open_folder_tab1.setStyleSheet("font-size: 18pt;")
        self.Open_folder_tab1.show()

        self.Open_folder = QPushButton("Open Folder", self.tab_2)
        self.Open_folder.setGeometry(2240, 1090, 201, 51)
        self.Open_folder.setStyleSheet("font-size: 18pt;")
        self.Open_folder.show()

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
        self.list_model_tab2 = QStringListModel()
        self.imageList_3.setModel(self.list_model_tab2)
        
        self.AvailableCams.currentIndexChanged.connect(self.tab2.on_camera_changed)
        self.CameraView.clicked.connect(self.tab2.open_camera)
        self.Take_a_Pic.clicked.connect(self.tab2.take_picture)
        self.ClearPoints.clicked.connect(self.tab2.clear_points_button)
        self.DeleteImage.clicked.connect(self.tab2.delete_selected_image)
        self.Calculate_points.clicked.connect(self.tab2.Calculate_3points)
        self.Open_folder.clicked.connect(self.tab2.open_folder)
        self.imageList_3.clicked.connect(self.tab2.show_selected_image_index)
        self.ExtrinsicCalibrate.clicked.connect(self.tab2.run_extrinsic_calibration)

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
            event.ignore()   # ✅ ESC is now ignored, program won’t quit
        else:
            super().keyPressEvent(event)
