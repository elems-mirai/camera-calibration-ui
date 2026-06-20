#!/usr/bin/env python3
"""Preview and record an undistorted IP-camera stream."""

from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CALIBRATION_PATH = PROJECT_ROOT / "Cameras" / "ip_camera" / "camera_data"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent / "output"
DEFAULT_HOST = "192.168.50.45"
DEFAULT_USERNAME = "admin"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show and record an undistorted IP-camera stream."
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="camera IP address")
    parser.add_argument("--username", default=DEFAULT_USERNAME, help="camera username")
    parser.add_argument(
        "--password",
        default=os.environ.get("CAMERA_PASSWORD"),
        help="camera password (prefer the CAMERA_PASSWORD environment variable)",
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
        help=f"video output directory (default: {DEFAULT_OUTPUT_PATH})",
    )
    return parser.parse_args()


def stream_url(args: argparse.Namespace, password: str) -> str:
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
    required = ["camera_matrix.npy", "distortion_coeff.npy"]
    missing = [name for name in required if not (path / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing calibration file(s) in {path}: {', '.join(missing)}"
        )

    camera_matrix = np.load(path / "camera_matrix.npy")
    distortion = np.load(path / "distortion_coeff.npy")
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
        url = stream_url(args, password)
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
    fps = camera.get(cv2.CAP_PROP_FPS)
    if not np.isfinite(fps) or fps < 1 or fps > 120:
        fps = 25.0

    map_x, map_y = cv2.initUndistortRectifyMap(
        camera_matrix,
        distortion,
        None,
        new_camera_matrix,
        (width, height),
        cv2.CV_32FC1,
    )

    args.output_path.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = args.output_path / f"undistorted_{timestamp}.mp4"
    # H.264 with yuv420p is widely supported. The dimensions must be even for
    # yuv420p, so discard at most one row or column from unusual frame sizes.
    video_width = width - (width % 2)
    video_height = height - (height % 2)
    encoder_command = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pixel_format",
        "bgr24",
        "-video_size",
        f"{video_width}x{video_height}",
        "-framerate",
        f"{fps:.3f}",
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_file),
    ]
    try:
        encoder = subprocess.Popen(encoder_command, stdin=subprocess.PIPE)
    except FileNotFoundError:
        camera.release()
        print("FFmpeg is required but was not found.", file=sys.stderr)
        return 1

    window_name = "Undistorted IP Camera - Recording"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 720)
    print(f"Recording undistorted video to: {output_file.resolve()}")
    print("Focus the preview window and press q or Esc to stop.")

    try:
        while ok and frame is not None:
            undistorted = cv2.remap(
                frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT
            )
            video_frame = undistorted[:video_height, :video_width]
            try:
                assert encoder.stdin is not None
                encoder.stdin.write(video_frame.tobytes())
            except (BrokenPipeError, OSError):
                print("The H.264 encoder stopped unexpectedly.", file=sys.stderr)
                break

            preview = undistorted.copy()
            cv2.circle(preview, (25, 30), 9, (0, 0, 255), -1)
            cv2.putText(
                preview,
                "REC    Q/ESC: stop",
                (45, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow(window_name, preview)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            ok, frame = camera.read()
    except KeyboardInterrupt:
        print()
    finally:
        camera.release()
        cv2.destroyAllWindows()
        if encoder.stdin is not None:
            encoder.stdin.close()
        encoder_result = encoder.wait()

    if encoder_result != 0:
        print("FFmpeg failed to finalize the output video.", file=sys.stderr)
        return 1
    print(f"Saved standard H.264 MP4: {output_file.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
