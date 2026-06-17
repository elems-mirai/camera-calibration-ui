import cv2
import os
import subprocess
from PyQt5.QtGui import QImage, QPixmap


def cvimg_to_qpixmap(img):
    """Convert OpenCV BGR image to QPixmap."""
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)


def _get_valid_camera_indices():
    """
    Return only real capture-capable camera indices.
    - Windows : probe 0–9 with CAP_DSHOW (no spam)
    - Linux   : check /dev/videoX via v4l2-ctl before opening,
                so metadata-only nodes are skipped silently.
    """
    valid = []

    if os.name == "nt":
        # Windows — CAP_DSHOW is clean, just probe
        for i in range(10):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                valid.append(i)
            cap.release()

    else:
        # Linux — filter with v4l2-ctl first to avoid FFMPEG/V4L2 spam
        for i in range(10):
            dev = f"/dev/video{i}"
            if not os.path.exists(dev):
                continue  # node doesn't exist at all → skip

            # Ask v4l2-ctl if this node supports Video Capture
            try:
                result = subprocess.run(
                    ["v4l2-ctl", "--device", dev, "--list-formats"],
                    capture_output=True, text=True, timeout=1
                )
                # Metadata/output-only nodes return empty or error output
                if not result.stdout.strip():
                    continue
            except (FileNotFoundError, subprocess.TimeoutExpired):
                # v4l2-ctl not installed → fall back to quiet V4L2 open
                pass

            # Only now open with V4L2 backend (no FFMPEG, no spam)
            cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
            if cap.isOpened():
                ret, _ = cap.read()   # confirm it can actually stream
                if ret:
                    valid.append(i)
                cap.release()

    print(f"[INFO] Detected cameras: {valid}")
    return valid


def detect_and_set_cameras(handler):
    """Detect cameras and populate Tab2 combo box (AvailableCams)."""
    combo = handler.ui.AvailableCams
    combo.clear()

    cameras = _get_valid_camera_indices()

    if cameras:
        for cam_id in cameras:
            combo.addItem(f"Camera {cam_id}", cam_id)
        combo.setCurrentIndex(0)
    else:
        combo.addItem("No camera detected")
        print("[WARN] No available cameras found.")


def detect_and_set_cameras_tab1(handler):
    """Detect cameras and populate Tab1 combo box (AvailableCams_tab1)."""
    combo = handler.ui.AvailableCams_tab1
    combo.clear()

    cameras = _get_valid_camera_indices()

    if cameras:
        for cam_id in cameras:
            combo.addItem(f"Camera {cam_id}", cam_id)
        combo.setCurrentIndex(0)
    else:
        combo.addItem("No camera detected")
        print("[WARN] No available cameras found.")
