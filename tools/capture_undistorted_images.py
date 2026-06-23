#!/usr/bin/env python3
"""Preview an undistorted IP-camera stream and capture corrected images."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote

# Snap-launched terminals can inject core20 libraries that are incompatible
# with the host Python/glibc. Restart once without those paths before importing
# OpenCV, because the dynamic loader reads LD_LIBRARY_PATH at process startup.
library_paths = os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep)
if any(path.startswith("/snap/") for path in library_paths):
    clean_environment = os.environ.copy()
    clean_paths = [path for path in library_paths if path and not path.startswith("/snap/")]
    if clean_paths:
        clean_environment["LD_LIBRARY_PATH"] = os.pathsep.join(clean_paths)
    else:
        clean_environment.pop("LD_LIBRARY_PATH", None)
    os.execve(sys.executable, [sys.executable, *sys.argv], clean_environment)

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CALIBRATION_PATH = PROJECT_ROOT / "camera" / "ip_camera" / "camera_data"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent / "output"
DEFAULT_HOST = "192.168.50.45"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "Mirai2025"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview and capture undistorted IP-camera images."
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="camera IP address")
    parser.add_argument("--username", default=DEFAULT_USERNAME, help="camera username")
    parser.add_argument(
        "--password",
        default=os.environ.get("CAMERA_PASSWORD", DEFAULT_PASSWORD),
        help="camera password (defaults to the configured camera password)",
    )
    parser.add_argument(
        "--stream-url",
        help="complete RTSP URL (credentials may be omitted)",
    )
    parser.add_argument(
        "--calibration-path",
        type=Path,
        default=DEFAULT_CALIBRATION_PATH,
        help=f"camera-data directory (default: {DEFAULT_CALIBRATION_PATH})",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"image output directory (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--prefix", default="undistorted_capture", help="saved filename prefix"
    )
    return parser.parse_args()


def make_stream_url(args: argparse.Namespace, password: str) -> str:
    if args.stream_url:
        if "://" not in args.stream_url:
            raise ValueError("--stream-url must include a scheme such as rtsp://")
        scheme, remainder = args.stream_url.split("://", 1)
        if "@" in remainder:
            return args.stream_url
        credentials = f"{quote(args.username, safe='')}:{quote(password, safe='')}@"
        return f"{scheme}://{credentials}{remainder}"

    credentials = f"{quote(args.username, safe='')}:{quote(password, safe='')}"
    return f"rtsp://{credentials}@{args.host}:554/Streaming/Channels/101"


def load_calibration(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    camera_matrix_path = path / "camera_matrix.npy"
    distortion_path = path / "distortion_coeff.npy"
    missing = [
        file.name
        for file in (camera_matrix_path, distortion_path)
        if not file.is_file()
    ]
    if missing:
        raise FileNotFoundError(
            f"Missing calibration file(s) in {path}: {', '.join(missing)}"
        )

    camera_matrix = np.load(camera_matrix_path)
    distortion = np.load(distortion_path)
    new_matrix_path = path / "new_camera_matrix.npy"
    new_camera_matrix = (
        np.load(new_matrix_path) if new_matrix_path.is_file() else camera_matrix.copy()
    )
    return camera_matrix, distortion, new_camera_matrix


def main() -> int:
    args = parse_args()
    password = args.password or getpass.getpass(
        f"Password for {args.username}@{args.host}: "
    )

    try:
        camera_matrix, distortion, new_camera_matrix = load_calibration(
            args.calibration_path
        )
        url = make_stream_url(args, password)
    except (FileNotFoundError, ValueError, OSError) as error:
        print(error, file=sys.stderr)
        return 1

    camera = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if not camera.isOpened():
        print("Could not open the camera stream.", file=sys.stderr)
        return 1

    ok, frame = camera.read()
    if not ok or frame is None:
        camera.release()
        print("Could not read the first camera frame.", file=sys.stderr)
        return 1

    height, width = frame.shape[:2]
    map_x, map_y = cv2.initUndistortRectifyMap(
        camera_matrix,
        distortion,
        None,
        new_camera_matrix,
        (width, height),
        cv2.CV_32FC1,
    )

    args.output_path.mkdir(parents=True, exist_ok=True)
    window_name = "Undistorted IP Camera Capture"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 720)
    print(f"Undistorted images will be saved in: {args.output_path.resolve()}")
    print("Focus the preview window. Press Enter to capture; press q or Esc to quit.")

    try:
        while ok and frame is not None:
            undistorted = cv2.remap(
                frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT
            )

            preview = undistorted.copy()
            cv2.putText(
                preview,
                "UNDISTORTED    ENTER: capture    Q/ESC: quit",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow(window_name, preview)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key in (10, 13):
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                milliseconds = int(time.time_ns() / 1_000_000) % 1000
                output_file = args.output_path / (
                    f"{args.prefix}_{timestamp}_{milliseconds:03d}.jpg"
                )
                if cv2.imwrite(str(output_file), undistorted):
                    print(f"Saved: {output_file.resolve()}")
                else:
                    print(f"Failed to save: {output_file}", file=sys.stderr)

            ok, frame = camera.read()
    except KeyboardInterrupt:
        print()
    finally:
        camera.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
