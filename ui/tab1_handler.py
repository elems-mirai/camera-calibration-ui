import os
import cv2
import time
from PyQt5.QtWidgets import QApplication, QFileDialog, QInputDialog, QLineEdit, QMessageBox
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import Qt
from utils.cv_utils import cvimg_to_qpixmap
from utils.camera_sources import (
    create_camera_source,
    default_camera_folder,
    ensure_camera_folder,
)
from utils import calibration

os.environ["QT_LOGGING_RULES"] = "qt.qpa.wayland.warning=false" 
class Tab1Handler:
    """Handles Tab1: image loading, camera control, and intrinsic calibration."""

    def __init__(self, main_ui):
        self.ui = main_ui
        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_camera_frame)
        self.fps = (1000 // self.ui.frame_rate)

        self.images = []
        self.image_names = []
        self.current_image_name = None
        self.current_original_image = None
        self.latest_frame = None
        self.capture_folder = None
        self.intrinsic_folder = None
        self.ui.camera_data = None
        self.current_source = "ip_camera"
        self._ip_password = os.environ.get("CAMERA_PASSWORD")

        self.ui.AvailableCams_tab1.clear()
        self.ui.AvailableCams_tab1.addItem("IP Camera", "ip_camera")
        self._apply_source_folder(self.current_source)

    # -------------------------------------------------
    # TAB CONTROL
    # -------------------------------------------------
    def on_tab_changed(self, index):
        """Clear Tab1 display when leaving the tab"""
        tab1_index = self.ui.tabWidget.indexOf(self.ui.tab)
        if index != tab1_index:
            if self.cap:
                self.close_camera()
            self.ui._display_target_tab1.clear()
            print("[Tab1] Cleared display because tab was changed")

    def open_folder(self):
        """Open folder dialog and set up extrinsic calibration directories."""
        try:
            # Create QFileDialog manually to ensure visibility and focus
            QApplication.setAttribute(Qt.AA_DontUseNativeMenuBar, True)

            # Open dialog
            base_dir = QFileDialog.getExistingDirectory(
                self.ui,
                "Select Save Folder",
                default_camera_folder(self.current_source),
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )

            # Exit if user cancelled
            if not base_dir:
                print("[INFO] No folder selected.")
                return

            self._apply_folder(base_dir)

            print(f"[Tab1] Folder opened: {base_dir}")

        except Exception as e:
            QMessageBox.critical(self.ui, "Error", f"Failed to open folder:\n{e}")
            print(f"[Tab1] Error during folder open: {e}")
    # -------------------------------------------------
    # CAMERA CONTROL
    # -------------------------------------------------
    def on_camera_changed(self):
        """Switch between the supported camera sources without probing webcams."""
        source_key = self.ui.AvailableCams_tab1.currentData()
        if source_key is None:
            return
        if self.cap:
            self.close_camera()
        self.current_source = source_key
        self._apply_source_folder(source_key)
        print(f"[Tab1] Source changed to {source_key}")

    def set_resolution_camera(self):
        """Resolution is controlled by the selected stream/topic."""
        return

    def open_camera(self):
        """Open current camera."""
        if self.cap is None:
            source_key = self.get_select_camera()
            password = self._get_ip_password() if source_key == "ip_camera" else None
            if source_key == "ip_camera" and not password:
                return
            try:
                self.cap = create_camera_source(source_key, password=password)
            except Exception as e:
                if source_key == "ip_camera":
                    self._ip_password = None
                QMessageBox.critical(self.ui, "Camera Error", str(e))
                self.cap = None
                return
            if not self.cap.isOpened():
                if source_key == "ip_camera":
                    self._ip_password = None
                    message = "Failed to open IP Camera. Check the password or RTSP settings."
                else:
                    message = f"Failed to open {source_key}."
                QMessageBox.warning(self.ui, "Camera Error", message)
                self.cap = None
                return
            self.set_resolution_camera()
        self.timer.start(self.fps)

    def close_camera(self):
        """Stop camera feed and clear the display."""
        if self.timer.isActive():
            self.timer.stop()
        if self.cap:
            self.cap.release()
            self.cap = None
        self.latest_frame = None
        self.ui._display_target_tab1.clear()
        print("[Tab1] Camera closed")

    def get_select_camera(self):
        """Return selected camera source key."""
        return self.ui.AvailableCams_tab1.currentData()

    def _get_ip_password(self):
        if self._ip_password:
            return self._ip_password
        password, ok = QInputDialog.getText(
            self.ui,
            "IP Camera Password",
            "Password:",
            QLineEdit.Password,
        )
        if ok and password:
            self._ip_password = password
            return password
        return None

    def _apply_source_folder(self, source_key):
        self._apply_folder(default_camera_folder(source_key))

    def _apply_folder(self, base_dir):
        ensure_camera_folder(base_dir)
        self.capture_folder = base_dir
        self.intrinsic_folder = os.path.join(base_dir, "intrinsic_images")
        self.ui.camera_data = os.path.join(base_dir, "camera_data")
        self.ui.points_csv = os.path.join(base_dir, "points.csv")
        self.images = []
        self.image_names = []
        self.load_images_from_directory(self.intrinsic_folder)

    def update_camera_frame(self):
        """Display live feed (optimized for ClickableLabel)."""
        if getattr(self.ui._display_target_tab1, "_dragging", False):
            return

        if self.cap:
            ret, frame = self.cap.read()
            if ret:
                self.latest_frame = frame.copy()
                self.ui._display_target_tab1._interaction_enabled = False

                if not getattr(self, "_camera_view_active", False):
                    self.ui._display_target_tab1.reset_view()
                    self._camera_view_active = True

                pixmap = cvimg_to_qpixmap(frame)
                self.ui._display_target_tab1.setPixmap(pixmap)



    # -------------------------------------------------
    # CAPTURE IMAGE
    # -------------------------------------------------
    def take_picture(self):
        """Capture and save image to intrinsic_images folder."""
        if not self.cap:
            self.open_camera()
        if not self.cap:
            print("[Tab1] Camera not open!")
            return

        frame = self.latest_frame.copy() if self.latest_frame is not None else None
        if frame is None:
            ret, frame = self.cap.read()
            if ret:
                self.latest_frame = frame.copy()
        if frame is None:
            print("[Tab1] Failed to capture")
            return

        # Folder safety
        if not self.intrinsic_folder:
            base_dir = QFileDialog.getExistingDirectory(self.ui, "Select Save Folder")
            if not base_dir:
                return
            self.capture_folder = base_dir
            self.intrinsic_folder = os.path.join(base_dir, "intrinsic_images")
            self.ui.camera_data = os.path.join(base_dir, "camera_data")
            os.makedirs(self.intrinsic_folder, exist_ok=True)
            os.makedirs(self.ui.camera_data, exist_ok=True)

        filename = f"capture_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
        save_path = os.path.join(self.intrinsic_folder, filename)
        cv2.imwrite(save_path, frame)

        if filename not in self.image_names:
            self.images.append(frame.copy())
            self.image_names.append(filename)
            self.ui.list_model.setStringList(self.image_names)
            print(f"[Tab1] Added new image: {filename}")
        else:
            print(f"[Tab1] Skipped duplicate image name: {filename}")

        self.flash_effect()
        self.display_image(frame)
        self.current_image_name = filename
        self.current_original_image = frame.copy()
        self.timer.start(self.fps)
        print(f"[Tab1] Captured and saved {filename}")

    def flash_effect(self):
        """Quick white flash after capture."""
        from PyQt5.QtGui import QPixmap, QColor
        w, h = self.ui._display_target_tab1.width(), self.ui._display_target_tab1.height()
        flash = QPixmap(w, h)
        flash.fill(QColor("white"))
        self.ui._display_target_tab1.setPixmap(flash)
        QApplication.processEvents()
        QTimer.singleShot(150, lambda: None)

    # -------------------------------------------------
    # IMAGE MANAGEMENT
    # -------------------------------------------------
    def load_images_from_directory(self, folder_path):
        """Load all images and show first one."""
        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)
            print(f"[INFO] Created folder: {folder_path}")
            return

        self.images.clear()
        self.image_names.clear()

        for filename in sorted(os.listdir(folder_path)):
            if filename.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                img_path = os.path.join(folder_path, filename)
                img = cv2.imread(img_path)
                if img is not None:
                    self.images.append(img)
                    self.image_names.append(filename)

        self.ui.list_model.setStringList(self.image_names)
        print(f"[Tab1] Loaded {len(self.images)} images from {folder_path}")

    def delete_selected_image(self):
        """Delete selected image from folder and UI."""
        if not self.current_image_name:
            print("[Tab1] No image selected to delete.")
            return

        image_name = self.current_image_name
        image_path = os.path.join(self.intrinsic_folder, image_name)

        reply = QMessageBox.question(
            self.ui,
            "Delete Image",
            f"Are you sure you want to delete '{image_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        if os.path.exists(image_path):
            try:
                os.remove(image_path)
                print(f"[Tab1] Deleted file: {image_path}")
            except Exception as e:
                print(f"[Tab1] Failed to delete: {e}")

        if image_name in self.image_names:
            idx = self.image_names.index(image_name)
            del self.image_names[idx]
            del self.images[idx]

        self.ui.list_model.setStringList(self.image_names)
        self.ui._display_target_tab1.clear()

        if self.image_names:
            next_idx = min(idx, len(self.image_names) - 1)
            self.current_image_name = self.image_names[next_idx]
            self.current_original_image = self.images[next_idx].copy()
            self.display_image(self.images[next_idx])
        else:
            self.current_image_name = None
            self.current_original_image = None
            print("[Tab1] All images deleted — reopening camera...")
            self.open_camera()

    def show_selected_image_index(self, index):
        row = index.row()
        if 0 <= row < len(self.images):
            if self.timer.isActive():
                self.timer.stop()

            self.current_image_name = self.image_names[row]
            self.current_original_image = self.images[row].copy()
            self.display_image(self.images[row])

            print(f"[Tab1] Current image set to: {self.current_image_name}")

    # -------------------------------------------------
    # DISPLAY & CALIBRATION
    # -------------------------------------------------
    def display_image(self, img):
        """Display captured/static image (zoom/pan enabled)."""
        self._camera_view_active = False
        self.ui._display_target_tab1._interaction_enabled = True
        pixmap = cvimg_to_qpixmap(img)
        self.ui._display_target_tab1.reset_view()
        self.ui._display_target_tab1.setPixmap(pixmap)



    def get_checkerboard_size(self):
        """Return checkerboard size (w, h)."""
        text = self.ui.CheckerBoardSizeBox.currentText().strip()
        if "x" in text:
            try:
                w, h = map(int, text.split("x"))
                return w, h
            except ValueError:
                print("[Tab1] Invalid checkerboard format!")
                return 0, 0
        return 0, 0

    def intrinsic_calibrate(self):
        """Run intrinsic calibration."""
        if self.current_source != "ip_camera":
            QMessageBox.information(
                self.ui,
                "Intrinsic Calibration",
                "Femto Bolt uses factory intrinsic calibration from camera_data.",
            )
            return
        checkerboard = self.get_checkerboard_size()
        if checkerboard == (0, 0):
            QMessageBox.warning(
                self.ui,
                "Invalid Checkerboard Size",
                "Enter checkerboard inner corners like 9x6 or 6x9.",
            )
            return
        self.ui.clear_cancel_request()
        calibration.intrinsic_calibrate(
            self.images,
            self.image_names,
            checkerboard,
            square_size=0.022,
            save_path=self.ui.camera_data,
            display_callback=self.display_image,
            cancel_callback=self.ui.should_cancel,
        )
