from __future__ import annotations

import csv
import os
from typing import List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPixmap
from PyQt5.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from calibration_val.image_canvas import ImageCanvas
from calibration_val.validator import ImgToWorldValidator, PointInput, PointResult


class ValidationWindow(QMainWindow):
    INPUT_PRECISION = 5
    TABLE_HEADERS = [
        "Point ID",
        "u",
        "v",
        "Expected X",
        "Expected Y",
        "Predicted X",
        "Predicted Y",
        "Error X",
        "Error Y",
        "Error Norm",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.image_path: Optional[str] = None
        self.camera_dir: Optional[str] = None
        self.original_pixmap: Optional[QPixmap] = None
        self.active_row: int = 0
        self._build_ui()
        self._apply_theme()

    def _build_ui(self) -> None:
        self.setWindowTitle("Calibration Validation - Phase 2")
        self.resize(1680, 980)

        central = QWidget(self)
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        left_panel = QVBoxLayout()
        left_panel.setSpacing(16)
        root.addLayout(left_panel, 0)

        control_group = QGroupBox("Inputs")
        control_layout = QFormLayout(control_group)
        control_layout.setSpacing(10)

        self.image_path_edit = QLineEdit()
        self.image_path_edit.setReadOnly(True)
        image_browse_btn = QPushButton("Select Image")
        image_browse_btn.clicked.connect(self.select_image)
        image_row = QHBoxLayout()
        image_row.addWidget(self.image_path_edit, 1)
        image_row.addWidget(image_browse_btn)
        control_layout.addRow("Image", image_row)

        self.camera_dir_edit = QLineEdit()
        self.camera_dir_edit.setReadOnly(True)
        camera_browse_btn = QPushButton("Select Camera Data")
        camera_browse_btn.clicked.connect(self.select_camera_dir)
        camera_row = QHBoxLayout()
        camera_row.addWidget(self.camera_dir_edit, 1)
        camera_row.addWidget(camera_browse_btn)
        control_layout.addRow("Camera Dir", camera_row)

        self.point_count_spin = QSpinBox()
        self.point_count_spin.setRange(1, 500)
        self.point_count_spin.setValue(1)
        control_layout.addRow("Point Count", self.point_count_spin)

        buttons_row = QGridLayout()
        self.generate_rows_btn = QPushButton("Generate Rows")
        self.generate_rows_btn.clicked.connect(self.generate_rows)
        buttons_row.addWidget(self.generate_rows_btn, 0, 0)

        self.load_csv_btn = QPushButton("Load CSV")
        self.load_csv_btn.clicked.connect(self.load_csv)
        buttons_row.addWidget(self.load_csv_btn, 0, 1)

        self.validate_btn = QPushButton("Validate")
        self.validate_btn.clicked.connect(self.validate_points)
        buttons_row.addWidget(self.validate_btn, 1, 0)

        self.export_btn = QPushButton("Export CSV")
        self.export_btn.clicked.connect(self.export_csv)
        buttons_row.addWidget(self.export_btn, 1, 1)
        control_layout.addRow(buttons_row)

        left_panel.addWidget(control_group)

        self.status_label = QLabel("Select an image and camera data folder, then choose a row and click the image.")
        self.status_label.setWordWrap(True)
        left_panel.addWidget(self.status_label)
        left_panel.addStretch(1)

        preview_group = QGroupBox("Image Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.image_preview = ImageCanvas()
        self.image_preview.set_click_callback(self.handle_image_click)
        preview_layout.addWidget(self.image_preview, 1)
        root.addWidget(preview_group, 2)

        table_group = QGroupBox("Points")
        table_layout = QVBoxLayout(table_group)
        self.points_table = QTableWidget(0, len(self.TABLE_HEADERS))
        self.points_table.setHorizontalHeaderLabels(self.TABLE_HEADERS)
        self.points_table.verticalHeader().setVisible(False)
        self.points_table.setAlternatingRowColors(True)
        self.points_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.points_table.setSelectionMode(QTableWidget.SingleSelection)
        self.points_table.itemSelectionChanged.connect(self._handle_table_selection_changed)
        table_layout.addWidget(self.points_table)
        root.addWidget(table_group, 1)

        self.generate_rows()

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #e8ece7;
            }
            QGroupBox {
                background: #f8f7f1;
                border: 1px solid #bcc8b8;
                border-radius: 10px;
                margin-top: 10px;
                font: 600 13px "Segoe UI";
                color: #223127;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
            QLabel {
                color: #223127;
                font: 12px "Segoe UI";
            }
            QLineEdit, QSpinBox, QTableWidget {
                background: #ffffff;
                border: 1px solid #bcc8b8;
                border-radius: 6px;
                padding: 6px;
                color: #172018;
            }
            QTableWidget::item:selected {
                background: #bfd6c2;
                color: #172018;
            }
            QPushButton {
                background: #355f4a;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                font: 600 12px "Segoe UI";
            }
            QPushButton:hover {
                background: #45775d;
            }
            QHeaderView::section {
                background: #d7e1d0;
                color: #223127;
                border: none;
                border-bottom: 1px solid #bcc8b8;
                padding: 6px;
                font: 600 11px "Segoe UI";
            }
            """
        )

    def select_image(self) -> None:
        image_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Validation Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        if not image_path:
            return

        self._reset_for_new_image()
        self.image_path = image_path
        self.image_path_edit.setText(image_path)
        self.original_pixmap = QPixmap(image_path)
        if self.original_pixmap.isNull():
            self.original_pixmap = None
            self.image_preview.clear_canvas()
            self._set_status("Failed to load the selected image.")
            return
        self._update_preview()
        csv_path = self._image_csv_path()
        if csv_path is not None and os.path.exists(csv_path):
            loaded = self._load_csv_path(csv_path, allow_empty=True)
            if loaded:
                self._set_status(
                    f"Loaded new image: {os.path.basename(image_path)}. Found and loaded CSV: {os.path.basename(csv_path)}."
                )
            else:
                self._initialize_empty_csv(csv_path)
                self._set_status(
                    f"Loaded new image: {os.path.basename(image_path)}. Existing CSV was empty, created a fresh CSV: {os.path.basename(csv_path)}."
                )
        elif csv_path is not None:
            self._initialize_empty_csv(csv_path)
            self._set_status(
                f"Loaded new image: {os.path.basename(image_path)}. Created new CSV: {os.path.basename(csv_path)}."
            )

    def select_camera_dir(self) -> None:
        camera_dir = QFileDialog.getExistingDirectory(self, "Select Camera Data Folder")
        if not camera_dir:
            return
        self.camera_dir = camera_dir
        self.camera_dir_edit.setText(camera_dir)
        self._set_status(f"Selected camera data: {camera_dir}")

    def generate_rows(self) -> None:
        count = self.point_count_spin.value()
        self.points_table.setRowCount(count)
        for row in range(count):
            self._set_readonly_item(row, 0, str(row + 1))
            for column in range(1, len(self.TABLE_HEADERS)):
                if self.points_table.item(row, column) is None:
                    self.points_table.setItem(row, column, QTableWidgetItem(""))
        self.points_table.resizeColumnsToContents()
        self.points_table.selectRow(0)
        self.active_row = 0
        self.image_preview.reset_points()
        self.image_preview.set_active_point(1)
        self._set_status(f"Prepared {count} point rows. Row 1 is active for image clicking.")

    def validate_points(self) -> None:
        if not self.camera_dir:
            self._show_error("Camera data folder is required.")
            return

        try:
            points, skipped_rows = self._collect_input_points()
            if not points:
                self._set_status("No complete rows to validate. Fill xi, yi, xw, yw in at least one row.")
                return
            validator = ImgToWorldValidator(self.camera_dir)
            results = validator.validate_points(points)
            self._apply_results(results)
            saved_path = self._auto_save_validation_csv()
            if skipped_rows:
                skipped_text = ", ".join(str(row) for row in skipped_rows)
                self._set_status(
                    f"Validated {len(results)} points. Saved CSV: {saved_path}. Skipped incomplete rows: {skipped_text}."
                )
            else:
                self._set_status(f"Validated {len(results)} points. Saved CSV: {saved_path}.")
        except Exception as exc:
            self._show_error(str(exc))

    def export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Validation CSV",
            "validation_summary.csv",
            "CSV Files (*.csv)",
        )
        if not path:
            return

        self._write_csv(path)
        self._set_status(f"Exported CSV: {path}")

    def _auto_save_validation_csv(self) -> str:
        if self.image_path:
            base_path = os.path.splitext(self.image_path)[0] + ".csv"
        else:
            base_path = os.path.join(os.getcwd(), "validation_summary.csv")

        self._write_csv(base_path)
        return base_path

    def _write_csv(self, path: str) -> None:
        headers = [
            "points",
            "xi",
            "yi",
            "xw",
            "yw",
            "x_error",
            "y_error",
        ]
        rows = []
        for row in range(self.points_table.rowCount()):
            rows.append(
                {
                    "points": self._cell_text(row, 0),
                    "xi": self._cell_text(row, 1),
                    "yi": self._cell_text(row, 2),
                    "xw": self._cell_text(row, 3),
                    "yw": self._cell_text(row, 4),
                    "x_error": self._cell_text(row, 7),
                    "y_error": self._cell_text(row, 8),
                }
            )

        with open(path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

    def load_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Points CSV",
            "",
            "CSV Files (*.csv)",
        )
        if not path:
            return

        try:
            loaded = self._load_csv_path(path, allow_empty=False)
            if loaded:
                self._set_status(f"Loaded CSV: {os.path.basename(path)}")
        except Exception as exc:
            self._show_error(f"Failed to load CSV: {exc}")

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_preview()

    def _collect_input_points(self) -> tuple[List[PointInput], List[int]]:
        points: List[PointInput] = []
        skipped_rows: List[int] = []
        for row in range(self.points_table.rowCount()):
            values = [self._cell_text(row, column) for column in (1, 2, 3, 4)]
            if all(value == "" for value in values):
                self._clear_result_cells(row)
                skipped_rows.append(row + 1)
                continue
            if any(value == "" for value in values):
                self._clear_result_cells(row)
                skipped_rows.append(row + 1)
                continue

            point_id = row + 1
            u = self._parse_float(row, 1, "u")
            v = self._parse_float(row, 2, "v")
            expected_x = self._parse_float(row, 3, "Expected X")
            expected_y = self._parse_float(row, 4, "Expected Y")
            points.append(
                PointInput(
                    point_id=point_id,
                    u=u,
                    v=v,
                    expected_x=expected_x,
                    expected_y=expected_y,
                )
            )
        return points, skipped_rows

    def _apply_results(self, results: List[PointResult]) -> None:
        for result in results:
            row = result.point_id - 1
            self._set_result_item(row, 5, result.predicted_x)
            self._set_result_item(row, 6, result.predicted_y)
            self._set_result_item(row, 7, result.error_x)
            self._set_result_item(row, 8, result.error_y)
            self._set_result_item(row, 9, result.error_norm)
        self.points_table.resizeColumnsToContents()

    def _set_readonly_item(self, row: int, column: int, value: str) -> None:
        item = QTableWidgetItem(value)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.points_table.setItem(row, column, item)

    def _set_result_item(self, row: int, column: int, value: float) -> None:
        item = QTableWidgetItem(f"{value:.1f}")
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.points_table.setItem(row, column, item)

    def _set_readonly_text(self, row: int, column: int, value: str) -> None:
        item = QTableWidgetItem(value)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.points_table.setItem(row, column, item)

    def _parse_float(self, row: int, column: int, name: str) -> float:
        value = self._cell_text(row, column)
        if value == "":
            raise ValueError(f"Row {row + 1}: {name} is required.")
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"Row {row + 1}: invalid {name} value '{value}'.") from exc

    def _cell_text(self, row: int, column: int) -> str:
        item = self.points_table.item(row, column)
        if item is None:
            return ""
        return item.text().strip()

    def _row_value(self, row: dict, keys: tuple[str, ...], default: str = "") -> str:
        normalized = {str(key).strip().lower(): "" if value is None else str(value).strip() for key, value in row.items()}
        for key in keys:
            value = normalized.get(key.lower())
            if value is not None:
                return value
        return default

    def _show_error(self, message: str) -> None:
        self._set_status(message)
        QMessageBox.critical(self, "Validation Error", message)

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def _update_preview(self) -> None:
        if self.original_pixmap is None:
            return
        self.image_preview.load_pixmap(self.original_pixmap)

    def _image_csv_path(self) -> Optional[str]:
        if not self.image_path:
            return None
        return os.path.splitext(self.image_path)[0] + ".csv"

    def _initialize_empty_csv(self, path: str) -> None:
        headers = ["points", "xi", "yi", "xw", "yw", "x_error", "y_error"]
        with open(path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(headers)

    def _load_csv_path(self, path: str, allow_empty: bool) -> bool:
        with open(path, "r", newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None:
                raise ValueError("CSV file has no header row.")
            rows = list(reader)

        if not rows:
            if allow_empty:
                return False
            raise ValueError("CSV file is empty.")

        self.point_count_spin.setValue(len(rows))
        self.generate_rows()

        for index, row in enumerate(rows):
            point_id = self._row_value(row, ("points", "point_id", "point", "id"), default=str(index + 1))
            xi = self._row_value(row, ("xi", "u", "x_image", "image_x"))
            yi = self._row_value(row, ("yi", "v", "y_image", "image_y"))
            xw = self._row_value(row, ("xw", "expected_x", "x", "world_x"))
            yw = self._row_value(row, ("yw", "expected_y", "y", "world_y"))
            x_error = self._row_value(row, ("x_error", "error_x"))
            y_error = self._row_value(row, ("y_error", "error_y"))

            self._set_readonly_item(index, 0, point_id)
            self._set_editable_text(index, 1, xi)
            self._set_editable_text(index, 2, yi)
            self._set_editable_text(index, 3, xw)
            self._set_editable_text(index, 4, yw)
            self._set_readonly_text(index, 5, "")
            self._set_readonly_text(index, 6, "")
            self._set_readonly_text(index, 7, x_error)
            self._set_readonly_text(index, 8, y_error)
            self._set_readonly_text(index, 9, "")

            if xi != "" and yi != "":
                try:
                    self.image_preview.set_point(index + 1, float(xi), float(yi))
                except ValueError:
                    pass

        self.points_table.selectRow(0)
        self.active_row = 0
        self.image_preview.set_active_point(1)
        self.points_table.resizeColumnsToContents()
        return True

    def _reset_for_new_image(self) -> None:
        self.camera_dir = None
        self.camera_dir_edit.clear()
        self.point_count_spin.setValue(1)
        self.points_table.clearContents()
        self.points_table.setRowCount(0)
        self.image_preview.clear_canvas()
        self.generate_rows()

    def handle_image_click(self, u: float, v: float) -> None:
        if self.points_table.rowCount() == 0:
            self._show_error("Generate point rows before clicking the image.")
            return

        row = self.active_row
        self._set_editable_text(row, 1, f"{u:.{self.INPUT_PRECISION}f}")
        self._set_editable_text(row, 2, f"{v:.{self.INPUT_PRECISION}f}")
        self.image_preview.set_point(row + 1, u, v)
        self.image_preview.set_active_point(row + 1)
        self._clear_result_cells(row)
        self._set_status(
            f"Assigned click to row {row + 1}: u={u:.{self.INPUT_PRECISION}f}, v={v:.{self.INPUT_PRECISION}f}. Click again to replace this point if needed."
        )

    def _handle_table_selection_changed(self) -> None:
        row = self.points_table.currentRow()
        if row < 0:
            return
        self.active_row = row
        self.image_preview.set_active_point(row + 1)
        self._set_status(
            f"Row {row + 1} is active. Click the image to set or replace that row's u and v values."
        )

    def _set_editable_text(self, row: int, column: int, value: str) -> None:
        item = self.points_table.item(row, column)
        if item is None:
            item = QTableWidgetItem(value)
            self.points_table.setItem(row, column, item)
        else:
            item.setText(value)

    def _clear_result_cells(self, row: int) -> None:
        for column in range(5, len(self.TABLE_HEADERS)):
            item = QTableWidgetItem("")
            item.setBackground(QColor("#fff5d6"))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.points_table.setItem(row, column, item)
