# ui/tab2_handler.py
import os
import cv2
import time
import pandas as pd
from PyQt5.QtWidgets import QFileDialog, QApplication, QMessageBox, QInputDialog, QLineEdit
from PyQt5.QtCore import QTimer

from utils.cv_utils import cvimg_to_qpixmap
from utils.camera_sources import (
    create_camera_source,
    default_camera_folder,
    ensure_camera_folder,
)
from utils.io_utils import save_points
from utils.calibration import extrinsic_calibrate

os.environ["QT_LOGGING_RULES"] = "qt.qpa.wayland.warning=false"


class Tab2Handler:
    def __init__(self, main_ui):
        self.ui = main_ui
        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_camera_frame)
        self.fps = (1000 // self.ui.frame_rate)
        self.ui.AvailableCams.clear()
        self.ui.AvailableCams.addItem("IP Camera", "ip_camera")
        self.ui.AvailableCams.addItem("Femto Bolt", "femto_bolt")

        self.images = []
        self.image_names = []
        self.current_image_name = None
        self.current_original_image = None
        self.latest_frame = None
        self.capture_folder = None
        self.extrinsic_folder = None
        self.current_camera_id = "ip_camera"
        self._camera_folders = {}
        self.ui.camera_data = None
        self.ui.points_csv = "points.csv"
        self._folder_selected = False 
        self._ip_password = os.environ.get("CAMERA_PASSWORD")
        self._apply_folder(default_camera_folder(self.current_camera_id), camera_id=self.current_camera_id)

        self._setup_validators()
        self._setup_point_connections()
        self.ui.imgPnt1.setChecked(True)

    # -------------------------------------------------
    # VALIDATORS
    # -------------------------------------------------
    def _setup_validators(self):
        """Float-only input; no commas allowed."""
        from PyQt5.QtGui import QRegExpValidator
        from PyQt5.QtCore import QRegExp
        regex = QRegExp(r"^-?\d*\.?\d*$")
        validator = QRegExpValidator(regex)
        for i in range(1, 7):
            getattr(self.ui, f"ImgPnt{i}X").setValidator(validator)
            getattr(self.ui, f"ImgPnt{i}Y").setValidator(validator)
            getattr(self.ui, f"WrldPnt{i}X").setValidator(validator)
            getattr(self.ui, f"WrldPnt{i}Y").setValidator(validator)
        print("[Tab2] Validators set.")

    # -------------------------------------------------
    # POINT CONNECTIONS
    # -------------------------------------------------
    def _setup_point_connections(self):
        """Wire returnPressed once per field. Click callback set separately."""
        self._point_map = {
            i: (
                getattr(self.ui, f"imgPnt{i}"),
                getattr(self.ui, f"ImgPnt{i}X"),
                getattr(self.ui, f"ImgPnt{i}Y"),
                getattr(self.ui, f"WrldPnt{i}X"),
                getattr(self.ui, f"WrldPnt{i}Y"),
            )
            for i in range(1, 7)
        }

        for i in range(1, 7):
            _, imgx, imgy, wrldx, wrldy = self._point_map[i]
            # capture i by default-arg to avoid closure-over-loop-var bug
            wrldx.returnPressed.connect(lambda _w=wrldy: _w.setFocus())
            wrldy.returnPressed.connect(lambda _i=i: self._on_world_point_entered(_i))

        self.ui._display_target_tab2.set_click_callback(self._on_image_clicked)
        print("[Tab2] Point connections wired.")

    def _on_image_clicked(self, x, y):
        """Handle a click on the image: fill the active point's image coords."""
        for i, (btn, imgx, imgy, wrldx, wrldy) in self._point_map.items():
            if not btn.isChecked():
                continue

            wx = wrldx.text().strip()
            wy = wrldy.text().strip()

            # If world coords already filled → advance to next point first
            if wx and wy:
                next_i = (i % 6) + 1
                self._point_map[next_i][0].setChecked(True)
                # Re-enter with the new active point
                self._on_image_clicked(x, y)
                return

            imgx.setText(str(x))
            imgy.setText(str(y))
            self.ui._display_target_tab2.add_point(i, x, y)
            self.auto_save_points()
            wrldx.setFocus()
            print(f"[Tab2] Clicked Point {i}: Img=({x}, {y})")
            break

    def _on_world_point_entered(self, i):
        """Called when user presses Enter on the world-Y field of point i."""
        _, _, _, wrldx, wrldy = self._point_map[i]
        wrldy.clearFocus()
        next_i = (i % 6) + 1
        self._point_map[next_i][0].setChecked(True)
        self.auto_save_points()
        print(f"[Tab2] World coords confirmed for Point {i} → switched to Point {next_i}")

    # -------------------------------------------------
    # TAB CONTROL
    # -------------------------------------------------
    def on_tab_changed(self, index):
        tab2_index = self.ui.tabWidget.indexOf(self.ui.tab_2)
        if index != tab2_index:
            if self.cap:
                self.close_camera()
            self.ui._display_target_tab2.clear()
            print("[Tab2] Cleared display on tab switch")

    # -------------------------------------------------
    # FOLDER
    # -------------------------------------------------
    def _apply_folder(self, base_dir, camera_id=None, load_images=True):
        ensure_camera_folder(base_dir)
        self.capture_folder = base_dir
        self.extrinsic_folder = os.path.join(base_dir, "extrinsic_images")
        self.ui.camera_data = os.path.join(base_dir, "camera_data")
        self.ui.points_csv = os.path.join(base_dir, "points.csv")

        if load_images:
            self.images, self.image_names = [], []
            self.load_images_from_directory(self.extrinsic_folder)

        self._folder_selected = True

        if camera_id is None:
            camera_id = self.current_camera_id
        if camera_id is not None:
            self._camera_folders[camera_id] = base_dir

    def open_folder(self):
        try:
            base_dir = QFileDialog.getExistingDirectory(
                self.ui, "Select Save Folder", default_camera_folder(self.current_camera_id),
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if not base_dir:
                return

            self._apply_folder(base_dir)
            print(f"[Tab2] Folder changed to: {base_dir}")

        except Exception as e:
            QMessageBox.critical(self.ui, "Error", f"Failed to open folder:\n{e}")

    # -------------------------------------------------
    # CAMERA
    # -------------------------------------------------
    def on_camera_changed(self):
        """Switch between the supported camera sources without probing webcams."""
        source_key = self.ui.AvailableCams.currentData()
        if source_key is None:
            return
        print(f"[Tab2] Source changed → {source_key}")

        self.current_camera_id = source_key

        if source_key in self._camera_folders:
            self._apply_folder(self._camera_folders[source_key], camera_id=source_key, load_images=True)
        else:
            self._apply_folder(default_camera_folder(source_key), camera_id=source_key, load_images=True)

        if self.cap:
            self.close_camera()

    def _update_resolution_box(self):
        """Resolution is controlled by the selected stream/topic."""
        return

    def open_camera(self):
        if self.cap is None:
            source_key = self.ui.AvailableCams.currentData()
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
            self._update_resolution_box()
        self.clear_points()
        self.timer.start(self.fps)

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

    def close_camera(self):
        if self.timer.isActive():
            self.timer.stop()
        if self.cap:
            self.cap.release()
            self.cap = None
        self.latest_frame = None
        self.ui._display_target_tab2.clear()
        print("[Tab2] Camera closed")

    def update_camera_frame(self):
        if getattr(self.ui._display_target_tab2, "_dragging", False):
            return
        if self.cap:
            ret, frame = self.cap.read()
            if ret:
                self.latest_frame = frame.copy()
                self.ui._display_target_tab2._interaction_enabled = False
                if not getattr(self, "_camera_view_active", False):
                    self.ui._display_target_tab2.reset_view()
                    self._camera_view_active = True
                pixmap = cvimg_to_qpixmap(frame)
                self.ui._display_target_tab2.setPixmap(pixmap)

    # -------------------------------------------------
    # CAPTURE
    # -------------------------------------------------
    def take_picture(self):
        self.ui.imgPnt1.setChecked(True)
        if not self.cap:
            self.open_camera()
        if not self.cap:
            print("[Tab2] Camera not open!")
            return

        frame = self.latest_frame.copy() if self.latest_frame is not None else None
        if frame is None:
            ret, frame = self.cap.read()
            if ret:
                self.latest_frame = frame.copy()
        if frame is None:
            print("[Tab2] Failed to capture")
            return

        if not self.capture_folder:
            self.capture_folder = QFileDialog.getExistingDirectory(self.ui, "Select Save Folder")
            if not self.capture_folder:
                return
            self._apply_folder(self.capture_folder, load_images=False)

        self.ui.camera_data = os.path.join(self.capture_folder, "camera_data")
        self.extrinsic_folder = os.path.join(self.capture_folder, "extrinsic_images")
        self.ui.points_csv = os.path.join(self.capture_folder, "points.csv")
        os.makedirs(self.ui.camera_data, exist_ok=True)
        os.makedirs(self.extrinsic_folder, exist_ok=True)

        if not self.images:
            self.load_images_from_directory(self.extrinsic_folder)

        filename = f"capture_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
        save_path = os.path.join(self.extrinsic_folder, filename)
        cv2.imwrite(save_path, frame)

        if filename not in self.image_names:
            self.images.append(frame.copy())
            self.image_names.append(filename)
            self.ui.list_model_tab2.setStringList(self.image_names)

        self.flash_effect()
        self.display_image(frame)
        self.current_image_name = filename
        self.current_original_image = frame.copy()
        self.timer.start(self.fps)
        print(f"[Tab2] Captured: {save_path}")

    def flash_effect(self):
        from PyQt5.QtGui import QPixmap, QColor
        w = self.ui._display_target_tab2.width()
        h = self.ui._display_target_tab2.height()
        flash = QPixmap(w, h)
        flash.fill(QColor("white"))
        self.ui._display_target_tab2.setPixmap(flash)
        QApplication.processEvents()
        QTimer.singleShot(150, lambda: None)

    # -------------------------------------------------
    # IMAGE MANAGEMENT
    # -------------------------------------------------
    def load_images_from_directory(self, folder_path=None):
        if not folder_path or folder_path is True or folder_path is False:
            folder_path = QFileDialog.getExistingDirectory(self.ui, "Select Image Folder")
            if not folder_path:
                return

        parent_dir = os.path.dirname(folder_path)
        self.capture_folder = parent_dir
        self.extrinsic_folder = folder_path
        self.ui.camera_data = os.path.join(parent_dir, "camera_data")
        self.ui.points_csv = os.path.join(parent_dir, "points.csv")
        self._folder_selected = True
        if self.current_camera_id is not None:
            self._camera_folders[self.current_camera_id] = parent_dir
        os.makedirs(self.ui.camera_data, exist_ok=True)

        self.images, self.image_names = [], []
        for fn in sorted(os.listdir(folder_path)):
            if fn.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                img = cv2.imread(os.path.join(folder_path, fn))
                if img is not None:
                    self.images.append(img)
                    self.image_names.append(fn)

        self.ui.list_model_tab2.setStringList(self.image_names)
        print(f"[Tab2] Loaded {len(self.images)} images")

    def show_selected_image_index(self, index):
        if not self.images:
            return
        row = index.row()
        if 0 <= row < len(self.images):
            if self.timer.isActive():
                self.timer.stop()
            self.current_image_name = self.image_names[row]
            self.current_original_image = self.images[row].copy()
            self.clear_points()
            self.display_image(self.images[row])
            self.load_existing_points(self.current_image_name)

    def display_image(self, img):
        self._camera_view_active = False
        self.ui._display_target_tab2._interaction_enabled = True
        pixmap = cvimg_to_qpixmap(img)
        self.ui._display_target_tab2.reset_view()
        self.ui._display_target_tab2.setPixmap(pixmap)

    # -------------------------------------------------
    # POINT MANAGEMENT
    # -------------------------------------------------
    def clear_points_button(self):
        """Clear displayed points and point fields for the current image."""
        self.ui.imgPnt1.setChecked(True)

        self.ui._display_target_tab2.clear_points()
        for i in range(1, 7):
            getattr(self.ui, f"ImgPnt{i}X").clear()
            getattr(self.ui, f"ImgPnt{i}Y").clear()
            getattr(self.ui, f"WrldPnt{i}X").clear()
            getattr(self.ui, f"WrldPnt{i}Y").clear()

        if not self.current_image_name:
            return

        csv_file = self.ui.points_csv
        if not os.path.exists(csv_file):
            return
        try:
            df = pd.read_csv(csv_file)
            mask = df["image_name"] == self.current_image_name
            df_img = df[mask]
            has_world = df_img[["xw", "yw"]].notna().any().any()
            if has_world:
                keep = df_img[df_img[["xw", "yw"]].notna().all(axis=1)][
                    ["image_name", "points", "xw", "yw"]
                ].reset_index(drop=True)
                df = pd.concat([df[~mask], keep], ignore_index=True)
            else:
                df = df[~mask]
            df.to_csv(csv_file, index=False)
        except Exception as e:
            print(f"[Tab2] CSV clear error: {e}")

    def delete_selected_image(self):
        if not self.current_image_name:
            return

        image_name = self.current_image_name

        if not self.extrinsic_folder:
            print("[Tab2] extrinsic_folder not set — cannot locate file to delete.")
        else:
            image_path = os.path.join(self.extrinsic_folder, image_name)
            reply = QMessageBox.question(
                self.ui, "Delete Image",
                f"Are you sure you want to delete '{image_name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception as e:
                    print(f"[Tab2] Failed to delete {image_path}: {e}")

        if image_name in self.image_names:
            idx = self.image_names.index(image_name)
            del self.image_names[idx]
            del self.images[idx]
        else:
            idx = 0

        csv_file = self.ui.points_csv
        if os.path.exists(csv_file):
            try:
                df = pd.read_csv(csv_file)
                df = df[df["image_name"] != image_name]
                df.to_csv(csv_file, index=False)
            except Exception as e:
                print(f"[Tab2] CSV update error: {e}")

        self.ui._display_target_tab2.clear()
        self.clear_points()
        self.ui.list_model_tab2.setStringList(self.image_names)

        if self.image_names:
            next_idx = min(idx, len(self.image_names) - 1)
            self.current_image_name = self.image_names[next_idx]
            self.current_original_image = self.images[next_idx].copy()
            self.display_image(self.images[next_idx])
            self.load_existing_points(self.current_image_name)
        else:
            self.current_image_name = None
            self.current_original_image = None
            self.open_camera()

    def clear_points(self):
        self.ui._display_target_tab2.clear_points()
        for i in range(1, 7):
            getattr(self.ui, f"ImgPnt{i}X").clear()
            getattr(self.ui, f"ImgPnt{i}Y").clear()
            getattr(self.ui, f"WrldPnt{i}X").clear()
            getattr(self.ui, f"WrldPnt{i}Y").clear()

    def load_existing_points(self, image_name):
        csv_file = self.ui.points_csv
        if not os.path.exists(csv_file):
            return
        try:
            df = pd.read_csv(csv_file)
            rows = df[df["image_name"] == image_name]
            self.ui._display_target_tab2.clear_points()

            n_points = len(rows)
            next_index = (n_points % 6) + 1
            self._point_map[next_index][0].setChecked(True)

            for _, row in rows.iterrows():
                pt = int(row["points"])
                if pt not in self._point_map:
                    continue
                xi, yi, xw, yw = row["xi"], row["yi"], row["xw"], row["yw"]
                if pd.notna(xi):
                    self._point_map[pt][1].setText(str(int(xi)))
                if pd.notna(yi):
                    self._point_map[pt][2].setText(str(int(yi)))
                if pd.notna(xw):
                    self._point_map[pt][3].setText(str(float(xw)))
                if pd.notna(yw):
                    self._point_map[pt][4].setText(str(float(yw)))
                if pd.notna(xi) and pd.notna(yi):
                    self.ui._display_target_tab2.add_point(pt, int(xi), int(yi))

            print(f"[Tab2] Loaded {len(rows)} points for {image_name}")
        except Exception as e:
            print(f"[Tab2] Error loading points: {e}")

    def auto_save_points(self):
        if self.current_image_name and not getattr(self, "_loading_points", False):
            self.save_set_points()

    def _safe_float(self, value: str):
        try:
            if not value:
                return None
            clean = value.replace(',', '.').strip()
            if clean.count('.') > 1:
                parts = clean.split('.')
                clean = parts[0] + '.' + ''.join(parts[1:])
            return float(clean)
        except ValueError:
            print(f"[Tab2] Invalid float: '{value}'")
            return None

    def save_set_points(self):
        if not self.current_image_name:
            return
        points_to_save = []
        for i in range(1, 7):
            x_text  = self._point_map[i][1].text().strip()
            y_text  = self._point_map[i][2].text().strip()
            xw_text = self._point_map[i][3].text().strip()
            yw_text = self._point_map[i][4].text().strip()
            if not (x_text or y_text or xw_text or yw_text):
                continue
            points_to_save.append({
                "image_name": self.current_image_name,
                "points": i,
                "xi": self._safe_float(x_text),
                "yi": self._safe_float(y_text),
                "xw": self._safe_float(xw_text),
                "yw": self._safe_float(yw_text),
            })
        if points_to_save:
            save_points(
                self.ui.points_csv,
                self.current_image_name,
                points_to_save,
                save_button=getattr(self.ui, "SaveSetPnt", None),
            )

    # -------------------------------------------------
    # CALIBRATION
    # -------------------------------------------------
    def run_extrinsic_calibration(self):
        try:
            points_csv = self.ui.points_csv
            save_path = self.ui.camera_data
            if not points_csv or not os.path.exists(points_csv):
                print("[Tab2] Points CSV not found!")
                return
            if not save_path or not os.path.exists(save_path):
                print("[Tab2] camera_data folder not found!")
                return
            rvec, tvec = extrinsic_calibrate(points_csv, save_path)
            if rvec is not None and tvec is not None:
                print(f"[Tab2] Calibration done\nrvec:\n{rvec}\ntvec:\n{tvec}")
            else:
                print("[Tab2] Calibration failed")
        except Exception as e:
            print(f"[Tab2] Calibration error: {e}")
