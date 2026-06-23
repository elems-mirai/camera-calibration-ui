import os
import cv2
import numpy as np
import pandas as pd
import math
from PyQt5.QtWidgets import (
    QFileDialog, QApplication, QMessageBox,
    QDialog, QVBoxLayout, QLabel, QFrame, QPushButton
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QColor
#----------------------------------------------------------
# INTRINSIC CALIBRATION
#----------------------------------------------------------

def intrinsic_calibrate(
    images,
    image_names,
    checkerboard,
    square_size,
    save_path,
    display_callback=None,
    image_paths=None,
    save_overlays=False,
    delete_failed=False,
    cancel_callback=None,
):
    """
    Perform camera intrinsic calibration from a list of images.

    Args:
        images (list[np.ndarray]): List of loaded BGR images.
        image_names (list[str]): Corresponding filenames for logging.
        checkerboard (tuple): Checkerboard size (width, height).
        square_size (float): Physical square size (e.g., 0.022 m).
        save_path (str): Directory to save calibration results.
        display_callback (callable): Optional function(img) to update UI preview.
    """
    import os, cv2, numpy as np

    # Handle missing or invalid save_path
    try:
        if save_path is None or not isinstance(save_path, str):
            raise AttributeError("Invalid or missing save_path")
        if not os.path.exists(save_path):
            os.makedirs(save_path)
    except AttributeError:
        save_path = os.path.join(os.getcwd(), "camera_data")
        os.makedirs(save_path, exist_ok=True)
        print(f"[Warning] 'camera_data' attribute not found. Using default: {save_path}")

    if not images:
        print("[Calibration] No images provided!")
        return None, None

    if not os.path.exists(save_path):
        os.makedirs(save_path)

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    threedpoints, twodpoints = [], []

    # Prepare object points
    objp = np.zeros((1, checkerboard[0] * checkerboard[1], 3), np.float32)
    objp[0, :, :2] = np.mgrid[0:checkerboard[0], 0:checkerboard[1]].T.reshape(-1, 2)
    objp *= square_size

    processed_images = []
    successful = 0
    kept_paths = []
    removed_paths = []
    # sms = None
    print(f"[Calibration] Starting intrinsic calibration...")
    print(f"[Calibration] Looking for {checkerboard[0]}x{checkerboard[1]} checkerboard")

    def is_cancelled():
        if cancel_callback is None:
            return False
        try:
            return bool(cancel_callback())
        except Exception:
            return False

    for idx, image in enumerate(images):
        QApplication.processEvents()
        if is_cancelled():
            print(f"[Calibration] Cancelled after {idx} / {len(images)} images.")
            return None, None

        print(f"[Calibration] Processing {idx + 1}/{len(images)}: {image_names[idx]}")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        ret, corners = cv2.findChessboardCorners(
            gray, checkerboard,
            cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK + cv2.CALIB_CB_NORMALIZE_IMAGE
        )
        if not ret and hasattr(cv2, "findChessboardCornersSB"):
            ret, corners = cv2.findChessboardCornersSB(
                gray,
                checkerboard,
                cv2.CALIB_CB_NORMALIZE_IMAGE,
            )

        QApplication.processEvents()
        if is_cancelled():
            print(f"[Calibration] Cancelled after {idx + 1} / {len(images)} images.")
            return None, None

        if ret:
            threedpoints.append(objp)
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            twodpoints.append(corners2)

            vis = cv2.drawChessboardCorners(image.copy(), checkerboard, corners2, ret)
            processed_images.append(vis)
            successful += 1
            print("[Calibration] Checkerboard detected")

            if display_callback:
                display_callback(vis)
            if save_overlays and image_paths:
                try:
                    cv2.imwrite(image_paths[idx], vis)
                except Exception as e:
                    print(f"[Calibration] Failed to save overlay: {e}")
            if image_paths:
                kept_paths.append(image_paths[idx])
        else:
            print("[Calibration] No checkerboard found")
            processed_images.append(image.copy())
            if delete_failed and image_paths:
                try:
                    os.remove(image_paths[idx])
                    removed_paths.append(image_paths[idx])
                except Exception as e:
                    print(f"[Calibration] Failed to delete image: {e}")

    print(f"[Calibration Summary] Detected checkerboard in {successful} out of {len(images)} images.")

    QApplication.processEvents()
    if is_cancelled():
        print("[Calibration] Cancelled before solve step.")
        return None, None

    if successful < 3:
        print("[Calibration] Error: Need at least 3 valid images!")
        intrinsic_show_popup(successful, len(images), calibration_rms=None, mean_error=None)
        return None, None

    # Calibration
    print("[Calibration] Running cv2.calibrateCamera...")
    calibration_rms, cameraMatrix, distCoeffs, rvecs, tvecs = cv2.calibrateCamera(
        threedpoints, twodpoints, gray.shape[::-1], None, None
    )

    if cameraMatrix is None or distCoeffs is None:
        print("[Calibration] Failed: cv2.calibrateCamera did not return valid matrices.")
        intrinsic_show_popup(successful, len(images), calibration_rms=None, mean_error=None)
        return None, None

    # Compute reprojection error
    mean_error = 0
    for i in range(len(threedpoints)):
        imgpoints2, _ = cv2.projectPoints(threedpoints[i], rvecs[i], tvecs[i], cameraMatrix, distCoeffs)
        mean_error += cv2.norm(twodpoints[i], imgpoints2, cv2.NORM_L2) / len(imgpoints2)
    mean_error /= len(threedpoints)
    print(f"[Calibration] OpenCV RMS reprojection error: {calibration_rms:.4f} px")
    print(f"[Calibration] Total reprojection error: {mean_error:.4f} px")


    # Save results
    np.save(os.path.join(save_path, "camera_matrix.npy"), cameraMatrix)
    np.save(os.path.join(save_path, "distortion_coeff.npy"), distCoeffs)

    h, w = images[0].shape[:2]
    new_cameraMatrix, roi = cv2.getOptimalNewCameraMatrix(cameraMatrix, distCoeffs, (w, h), 1, (w, h))
    np.save(os.path.join(save_path, "new_camera_matrix.npy"), new_cameraMatrix)
    np.save(os.path.join(save_path, "roi.npy"), roi)

    print("[Calibration] Results saved in", os.path.abspath(save_path))
    intrinsic_show_popup(successful, len(images), calibration_rms=calibration_rms, mean_error=mean_error)

    return cameraMatrix, distCoeffs

#----------------------------------------------------------
# INTRINSIC REPORT
#----------------------------------------------------------
def intrinsic_show_popup(successful, total, calibration_rms=None, mean_error=None):
    """Show intrinsic calibration summary in a popup and print the same values to stdout."""
    failed = total - successful

    if mean_error is None:
        quality = "N/A"
        advice = "Need at least 3 valid checkerboard images to calibrate."
        color = "#888888"
    elif mean_error < 0.1:
        quality = "Excellent"
        advice = "Great calibration, ready to use."
        color = "#27ae60"
    elif mean_error < 0.5:
        quality = "Good"
        advice = "Acceptable. More images may improve accuracy."
        color = "#f1c40f"
    elif mean_error < 1.0:
        quality = "Medium"
        advice = "Consider recapturing with better lighting or angles."
        color = "#e67e22"
    else:
        quality = "Poor"
        advice = "High error. Retake images and verify checkerboard size."
        color = "#e74c3c"

    print("[Calibration Report] Intrinsic calibration summary")
    print(f"[Calibration Report] Total images: {total}")
    print(f"[Calibration Report] Successful detections: {successful}")
    print(f"[Calibration Report] Failed / deleted: {failed}")
    if calibration_rms is not None:
        print(f"[Calibration Report] OpenCV RMS: {calibration_rms:.4f} px")
    if mean_error is not None:
        print(f"[Calibration Report] Mean reprojection error: {mean_error:.4f} px")
        print(f"[Calibration Report] Quality: {quality}")
    else:
        print("[Calibration Report] Mean reprojection error: N/A")
        print("[Calibration Report] Quality: N/A")
    print(f"[Calibration Report] Advice: {advice}")

    app = QApplication.instance()
    if app is None:
        print("[Popup] Skipped intrinsic popup (no QApplication).")
        return

    calibration_ok = (mean_error is not None and calibration_rms is not None)

    dialog = QDialog()
    dialog.setWindowTitle(
        "Intrinsic Calibration Successful" if calibration_ok else "Intrinsic Calibration Warning"
    )
    dialog.setMinimumWidth(500)
    dialog.setStyleSheet("background-color: #1e1e1e; color: #f0f0f0;")

    layout = QVBoxLayout(dialog)
    layout.setSpacing(12)
    layout.setContentsMargins(20, 20, 20, 20)

    title = QLabel(
        "Intrinsic Calibration Complete" if calibration_ok else "Intrinsic Calibration Warning"
    )
    title.setAlignment(Qt.AlignCenter)
    title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #f0f0f0;")
    layout.addWidget(title)

    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("color: #444444;")
    layout.addWidget(line)

    stats_text = (
        f"Total images: {total}\n"
        f"Successful detections: {successful}\n"
        f"Failed / deleted: {failed}"
    )
    stats_label = QLabel(stats_text)
    stats_label.setAlignment(Qt.AlignLeft)
    stats_label.setStyleSheet("font-size: 11pt; color: #f0f0f0;")
    layout.addWidget(stats_label)

    metric_lines = []
    if calibration_rms is not None:
        metric_lines.append(f"OpenCV RMS reprojection error: {calibration_rms:.4f} px")
    else:
        metric_lines.append("OpenCV RMS reprojection error: N/A")

    if mean_error is not None:
        metric_lines.append(f"Mean reprojection error: {mean_error:.4f} px")
        metric_lines.append(f"Quality: {quality}")
    else:
        metric_lines.append("Mean reprojection error: N/A")
        metric_lines.append("Quality: N/A")

    metric_box = QLabel("\n".join(metric_lines))
    metric_box.setAlignment(Qt.AlignCenter)
    metric_box.setStyleSheet(
        f"background-color: {color}22;"
        f"border: 2px solid {color};"
        f"border-radius: 10px;"
        f"padding: 14px;"
        f"font-size: 11pt;"
        f"font-weight: bold;"
        f"color: #f0f0f0;"
    )
    layout.addWidget(metric_box)

    advice_label = QLabel(advice)
    advice_label.setWordWrap(True)
    advice_label.setAlignment(Qt.AlignCenter)
    advice_label.setStyleSheet("font-size: 10pt; color: #cfcfcf;")
    layout.addWidget(advice_label)

    ok_btn = QPushButton("OK")
    ok_btn.setFixedHeight(36)
    ok_btn.setStyleSheet(
        f"background-color: {color}; color: white; font-size: 11pt; font-weight: bold; border-radius: 6px;"
    )
    ok_btn.clicked.connect(dialog.accept)
    layout.addWidget(ok_btn)

    dialog.exec_()


#----------------------------------------------------------
# EXTRINSIC CALIBRATION
#----------------------------------------------------------
def extrinsic_calibrate(points_csv, save_path):

    try:
        if save_path is None or not isinstance(save_path, str):
            raise AttributeError
        if not os.path.exists(save_path):
            os.makedirs(save_path)
    except AttributeError:
        save_path = os.path.join(os.getcwd(), "camera_data")
        os.makedirs(save_path, exist_ok=True)

    if not os.path.exists(points_csv):
        print("[Calibration] No points CSV found!")
        return None, None

    dist_coeff   = np.load(os.path.join(save_path, "distortion_coeff.npy"))
    cameraMatrix = np.load(os.path.join(save_path, "camera_matrix.npy"))

    df = pd.read_csv(points_csv)

    # Drop any row where xi, yi, xw, or yw is missing
    df_clean = df.dropna(subset=["xi", "yi", "xw", "yw"])
    print(f"[Calibration] Valid points: {len(df_clean)} / {len(df)}")

    if len(df_clean) < 4:
        print("[Calibration] Not enough valid points (need >= 4)!")
        return None, None

    object_points = df_clean[["xw", "yw"]].values.astype(np.float32)
    object_points = np.hstack([object_points,
                                np.zeros((object_points.shape[0], 1), dtype=np.float32)])
    image_points  = df_clean[["xi", "yi"]].values.astype(np.float32)

    # ── solvePnP with IPPE (best for coplanar/Z=0 points) ──
    
    ret, rvec, tvec = cv2.solvePnP(
        object_points,
        image_points,
        cameraMatrix,
        dist_coeff,
        flags=cv2.SOLVEPNP_IPPE
    )
 
    if not ret:
        print("[Calibration] solvePnP failed!")
        return None, None

    # ── Refine with VVS ──
    # cv2.solvePnPRefineVVS(
    #     object_points,
    #     image_points,
    #     cameraMatrix,
    #     dist_coeff,
    #     rvec,
    #     tvec
    # )
    # Step 2: refine with LM
    cv2.solvePnPRefineLM(
        object_points,
        image_points,
        cameraMatrix,
        dist_coeff,
        rvec,
        tvec
    )

    # ── Reprojection error check ──
    projected, _ = cv2.projectPoints(object_points, rvec, tvec, cameraMatrix, dist_coeff)
    projected     = projected.reshape(-1, 2)
    errors        = np.linalg.norm(image_points - projected, axis=1)
    print(f"[Calibration] Reprojection error — mean: {errors.mean():.3f}px  "
          f"max: {errors.max():.3f}px  min: {errors.min():.3f}px")

    rotationMatrix, _ = cv2.Rodrigues(rvec)
    Rt         = np.column_stack((rotationMatrix, tvec))
    projMatrix = cameraMatrix.dot(Rt)

    np.save(os.path.join(save_path, "rvec.npy"),              rvec)
    np.save(os.path.join(save_path, "tvec.npy"),              tvec)
    np.save(os.path.join(save_path, "rotation_matrix.npy"),   rotationMatrix)
    np.save(os.path.join(save_path, "Rt_matrix.npy"),         Rt)
    np.save(os.path.join(save_path, "projection_matrix.npy"), projMatrix)

    print("[Calibration] Extrinsic calibration saved in", os.path.abspath(save_path))
    sms_data = error_checker(save_path, points_csv)
    extrinsic_show_popup(sms_data)
    return rvec, tvec
#----------------------------------------------------------
# EXTRINSIC POPUP
#----------------------------------------------------------

def extrinsic_show_popup(data):
    app = QApplication.instance()
    if app is None:
        print("[Popup] Skipped extrinsic popup (no QApplication).")
        return

    all_errs_A, all_errs_B = [], []
    for row in data:
        all_errs_A.append(math.sqrt(row["A_Error_X"]**2 + row["A_Error_Y"]**2))
        all_errs_B.append(math.sqrt(row["B_Error_X"]**2 + row["B_Error_Y"]**2))

    def _band(err):
        if math.isnan(err) or np.isinf(err):
            return "N/A", "#666666"
        if err < 0.5:
            return "Excellent", "#2b8a3e"
        if err < 1.0:
            return "Good", "#7a5b00"
        if err < 2.0:
            return "Medium", "#b45f06"
        return "Poor", "#d9534f"

    mean_A = sum(all_errs_A) / len(all_errs_A) if all_errs_A else float("nan")
    mean_B = sum(all_errs_B) / len(all_errs_B) if all_errs_B else float("nan")
    label_A, color_A = _band(mean_A)
    label_B, color_B = _band(mean_B)

    from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                  QPushButton, QLabel, QFrame, QSizePolicy,
                                  QTableWidget, QTableWidgetItem, QHeaderView)
    from PyQt5.QtCore import Qt as _Qt

    dialog = QDialog()
    dialog.setWindowTitle("Extrinsic Calibration Results")
    dialog.resize(1180, 650)
    dialog.setMinimumSize(960, 520)
    dialog.setStyleSheet(
        """
        QDialog {
            background-color: #ececec;
            color: #222222;
            font-family: "Segoe UI", "Ubuntu", sans-serif;
        }
        QLabel {
            font-size: 12px;
        }
        QTableWidget {
            background-color: #ffffff;
            alternate-background-color: #f8f8f8;
            color: #111111;
            font-family: "Consolas", "Courier New", "Monaco", monospace;
            font-size: 12px;
            border: 1px solid #bcbcbc;
            gridline-color: #dcdcdc;
            selection-background-color: #d8e8f7;
            selection-color: #111111;
        }
        QHeaderView::section {
            background-color: #e0e0e0;
            color: #222222;
            padding: 5px;
            font-weight: 700;
            border: 1px solid #bcbcbc;
        }
        QFrame#metric_card {
            background-color: #ffffff;
            border: 1px solid #bcbcbc;
            border-radius: 4px;
        }
        QPushButton#action_btn {
            background-color: #005a9e;
            color: #ffffff;
            border: 1px solid #004b85;
            font-weight: bold;
            padding: 6px 20px;
            border-radius: 2px;
            font-size: 12px;
        }
        QPushButton#action_btn:hover {
            background-color: #0063ad;
        }
        """
    )

    outer = QVBoxLayout(dialog)
    outer.setSpacing(14)
    outer.setContentsMargins(16, 16, 16, 16)

    title = QLabel("Extrinsic Calibration - Dual Method Error Report")
    title.setStyleSheet("font-size: 14px; font-weight: 700; color: #222222;")
    outer.addWidget(title)

    headers = [
        "Image",
        "u",
        "v",
        "X",
        "Y",
        "A Pred X",
        "A Pred Y",
        "A Err X",
        "A Err Y",
        "B Pred X",
        "B Pred Y",
        "B Err X",
        "B Err Y",
    ]
    table = QTableWidget(len(data), len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setSelectionMode(QTableWidget.SingleSelection)
    table.setEditTriggers(QTableWidget.NoEditTriggers)

    def set_table_item(row_idx, col_idx, value, numeric=False):
        if numeric:
            try:
                text = f"{float(value):.3f}"
            except (TypeError, ValueError):
                text = str(value)
        else:
            text = str(value)

        item = QTableWidgetItem(text)
        item.setTextAlignment(_Qt.AlignRight | _Qt.AlignVCenter if numeric else _Qt.AlignLeft | _Qt.AlignVCenter)
        table.setItem(row_idx, col_idx, item)

    for row_idx, row in enumerate(data):
        values = [
            (row["Image name"], False),
            (row["u"], True),
            (row["v"], True),
            (row["Correct_X"], True),
            (row["Correct_Y"], True),
            (row["A_Predicted_X"], True),
            (row["A_Predicted_Y"], True),
            (row["A_Error_X"], True),
            (row["A_Error_Y"], True),
            (row["B_Predicted_X"], True),
            (row["B_Predicted_Y"], True),
            (row["B_Error_X"], True),
            (row["B_Error_Y"], True),
        ]
        for col_idx, (value, numeric) in enumerate(values):
            set_table_item(row_idx, col_idx, value, numeric=numeric)

    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.Interactive)
    header.setStretchLastSection(False)
    table.setColumnWidth(0, 220)
    for col in range(1, len(headers)):
        table.setColumnWidth(col, 82)
    table.resizeRowsToContents()
    outer.addWidget(table, 1)

    cards_row = QHBoxLayout()
    cards_row.setSpacing(16)

    def build_metric_card(method, subtitle, mean_err, label, color):
        card = QFrame()
        card.setObjectName("metric_card")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        title_label = QLabel(method)
        title_label.setAlignment(_Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #333333;")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setAlignment(_Qt.AlignCenter)
        subtitle_label.setStyleSheet("font-size: 11px; color: #777777;")

        status_label = QLabel(label)
        status_label.setAlignment(_Qt.AlignCenter)
        status_label.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {color};")

        rmse_label = QLabel(f"RMSE = {mean_err:.4f} px")
        rmse_label.setAlignment(_Qt.AlignCenter)
        rmse_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #222222;")

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addSpacing(6)
        layout.addWidget(status_label)
        layout.addWidget(rmse_label)
        return card

    for method, subtitle, mean_err, label, color in [
        ("Method A", "original K + distortion", mean_A, label_A, color_A),
        ("Method B", "new K / undistorted image", mean_B, label_B, color_B),
    ]:
        cards_row.addWidget(build_metric_card(method, subtitle, mean_err, label, color))

    outer.addLayout(cards_row)

    button_row = QHBoxLayout()
    button_row.addStretch(1)
    ok_btn = QPushButton("OK")
    ok_btn.setObjectName("action_btn")
    ok_btn.setMinimumWidth(120)
    ok_btn.clicked.connect(dialog.accept)
    button_row.addWidget(ok_btn)
    outer.addLayout(button_row)

    dialog.exec_()
#----------------------------------------------------------
# Error checker
#----------------------------------------------------------
def error_checker(camera_data, csv_path):
    """
    Run two parallel back-projection methods and return both results.

    Method A — Original (distorted pixel space):
        undistortPoints(..., P=cameraMatrix) + inv(cameraMatrix) + inv(R)

    Method B — Undistorted image space:
        undistortPoints(..., P=new_cameraMatrix) + inv(new_cameraMatrix) + inv(R)
    """
    # ── Load calibration files ───────────────────────────────────
    cameraMatrix     = np.load(os.path.join(camera_data, "camera_matrix.npy"))
    new_cameraMatrix = np.load(os.path.join(camera_data, "new_camera_matrix.npy"))
    dist_coeffs      = np.load(os.path.join(camera_data, "distortion_coeff.npy"))
    tvec             = np.load(os.path.join(camera_data, "tvec.npy")).reshape(3, 1)
    R_matrix         = np.load(os.path.join(camera_data, "rotation_matrix.npy"))

    inv_K_orig = np.linalg.inv(cameraMatrix)
    inv_K_new  = np.linalg.inv(new_cameraMatrix)
    inv_R      = np.linalg.inv(R_matrix)

    df = pd.read_csv(csv_path).dropna(subset=["xi", "yi", "xw", "yw"])

    # ── Shared ray-casting logic ─────────────────────────────────
    def _ray_to_world(u_undist, v_undist, inv_K):
        """Back-project an undistorted pixel to Z=0 world plane."""
        uv1   = np.array([[u_undist], [v_undist], [1.0]], dtype=np.float64)

        # Two points on the ray (scaling = 0 and 1)
        A = inv_R.dot(inv_K.dot(0 * uv1) - tvec).flatten()
        B = inv_R.dot(inv_K.dot(1 * uv1) - tvec).flatten()

        eq = (0.0 - A[2]) / (B[2] - A[2])
        Xw = eq * (B[0] - A[0]) + A[0]
        Yw = eq * (B[1] - A[1]) + A[1]
        return float(Xw), float(Yw)

    # ── Method A helpers (original cameraMatrix) ─────────────────
    def undistort_A(u, v):
        """Undistort and keep in original camera pixel space."""
        pts = np.array([[[u, v]]], dtype=np.float64)
        out = cv2.undistortPoints(pts, cameraMatrix, dist_coeffs,
                                  P=cameraMatrix)
        return float(out[0, 0, 0]), float(out[0, 0, 1])

    def img2world_A(u, v):
        uu, vu = undistort_A(u, v)
        return _ray_to_world(uu, vu, inv_K_orig)

    # ── Method B helpers (new_cameraMatrix / undistorted image) ──
    def undistort_B(u, v):
        """Undistort and reproject into new (undistorted) image space."""
        pts = np.array([[[u, v]]], dtype=np.float64)
        out = cv2.undistortPoints(pts, cameraMatrix, dist_coeffs,
                                  P=new_cameraMatrix)
        return float(out[0, 0, 0]), float(out[0, 0, 1])

    def img2world_B(u, v):
        uu, vu = undistort_B(u, v)
        return _ray_to_world(uu, vu, inv_K_new)

    # ── Run both methods on every point ─────────────────────────
    data = []

    for name, group in df.groupby("image_name"):
        obj_pts = group[["xw", "yw"]].values
        obj_pts = np.hstack([obj_pts, np.zeros((len(obj_pts), 1))])
        img_pts = group[["xi", "yi"]].values

        print(f"\n{'─'*50} {name}")
        print(f"  {'u':>6} {'v':>6} | "
              f"{'Correct':>14} | "
              f"{'Method-A':>14} {'Err-A':>10} | "
              f"{'Method-B':>14} {'Err-B':>10}")
        print(f"  {'─'*110}")

        for i in range(len(img_pts)):
            u, v   = img_pts[i]
            cx, cy = float(obj_pts[i][0]), float(obj_pts[i][1])

            # Method A
            Xw_A, Yw_A = img2world_A(u, v)
            ex_A = round(cx - Xw_A, 3)
            ey_A = round(cy - Yw_A, 3)

            # Method B
            Xw_B, Yw_B = img2world_B(u, v)
            ex_B = round(cx - Xw_B, 3)
            ey_B = round(cy - Yw_B, 3)

            print(
                f"  {u:>6.1f} {v:>6.1f} | "
                f"[{cx:>6.2f},{cy:>6.2f}] | "
                f"A:[{Xw_A:>6.2f},{Yw_A:>6.2f}] "
                f"err:[{ex_A:>7.3f},{ey_A:>7.3f}] | "
                f"B:[{Xw_B:>6.2f},{Yw_B:>6.2f}] "
                f"err:[{ex_B:>7.3f},{ey_B:>7.3f}]"
            )

            data.append({
                # Identity
                "Image name":   name,
                "u":            float(u),
                "v":            float(v),
                # Ground truth
                "Correct_X":    cx,
                "Correct_Y":    cy,
                "Correct_Z":    0.0,
                # Method A
                "A_Predicted_X": round(Xw_A, 3),
                "A_Predicted_Y": round(Yw_A, 3),
                "A_Error_X":     ex_A,
                "A_Error_Y":     ey_A,
                # Method B
                "B_Predicted_X": round(Xw_B, 3),
                "B_Predicted_Y": round(Yw_B, 3),
                "B_Error_X":     ex_B,
                "B_Error_Y":     ey_B,
            })

    # ── Print summary ────────────────────────────────────────────
    if data:
        errs_A = [abs(d["A_Error_X"]) + abs(d["A_Error_Y"]) for d in data]
        errs_B = [abs(d["B_Error_X"]) + abs(d["B_Error_Y"]) for d in data]
        print(f"\n[ErrorChecker] Method A mean abs error: "
              f"{sum(errs_A)/len(errs_A):.4f}")
        print(f"[ErrorChecker] Method B mean abs error: "
              f"{sum(errs_B)/len(errs_B):.4f}")

    return data
