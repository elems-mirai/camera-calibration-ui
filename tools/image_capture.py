#!/usr/bin/env python3
"""Capture undistorted IP-camera images as sequential JPG files.

Live preview uses the low-bandwidth sub stream by default. Saved images are read
fresh from the high-quality main stream and are not mirrored.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path
from urllib.parse import quote

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
        description="Preview IP-camera sub stream and capture high-quality images."
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="camera IP address")
    parser.add_argument("--username", default=DEFAULT_USERNAME, help="camera username")
    parser.add_argument(
        "--password",
        default=os.environ.get("CAMERA_PASSWORD", DEFAULT_PASSWORD),
        help="camera password",
    )
    parser.add_argument(
        "--preview-stream-url",
        help="complete low-latency preview RTSP URL; default uses channel 102",
    )
    parser.add_argument(
        "--capture-stream-url",
        help="complete high-quality capture RTSP URL; default uses channel 101",
    )
    parser.add_argument(
        "--stream-url",
        help="legacy option: use this URL for both preview and capture",
    )
    parser.add_argument(
        "--preview-channel",
        default="102",
        help="RTSP channel for low-latency preview (default: 102)",
    )
    parser.add_argument(
        "--capture-channel",
        default="101",
        help="RTSP channel for high-quality capture (default: 101)",
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
        "--preview-drain-frames",
        type=int,
        default=int(os.environ.get("IP_CAMERA_PREVIEW_DRAIN_FRAMES", "1")),
        help="number of stale preview frames to drop before display",
    )
    parser.add_argument(
        "--capture-drain-frames",
        type=int,
        default=int(os.environ.get("IP_CAMERA_CAPTURE_DRAIN_FRAMES", "2")),
        help="number of stale high-quality frames to drop before saving",
    )
    parser.add_argument(
        "--capture-timeout-frames",
        type=int,
        default=30,
        help="maximum frame attempts when reading a high-quality capture",
    )
    parser.add_argument(
        "--close-capture-between-shots",
        action="store_true",
        help="close the high-quality stream after each shot to reduce CPU/network use",
    )
    parser.add_argument(
        "--no-mirror-preview",
        action="store_true",
        help="disable horizontal mirror in the preview window",
    )
    parser.add_argument("--expected-width", type=int, default=2688)
    parser.add_argument("--expected-height", type=int, default=1520)
    return parser.parse_args()


def rtsp_url(host: str, username: str, password: str, channel: str) -> str:
    credentials = f"{quote(username, safe='')}:{quote(password, safe='')}"
    return f"rtsp://{credentials}@{host}:554/Streaming/Channels/{channel}"


def with_credentials(url: str, username: str, password: str) -> str:
    if "://" not in url:
        raise ValueError("RTSP URL must include a scheme such as rtsp://")
    scheme, remainder = url.split("://", 1)
    if "@" in remainder:
        return url
    credentials = f"{quote(username, safe='')}:{quote(password, safe='')}@"
    return f"{scheme}://{credentials}{remainder}"


def make_stream_urls(args: argparse.Namespace, password: str) -> tuple[str, str]:
    if args.stream_url:
        url = with_credentials(args.stream_url, args.username, password)
        return url, url

    preview_url = (
        with_credentials(args.preview_stream_url, args.username, password)
        if args.preview_stream_url
        else rtsp_url(args.host, args.username, password, args.preview_channel)
    )
    capture_url = (
        with_credentials(args.capture_stream_url, args.username, password)
        if args.capture_stream_url
        else rtsp_url(args.host, args.username, password, args.capture_channel)
    )
    return preview_url, capture_url


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


def next_output_path(output_dir: Path) -> Path:
    max_index = -1
    for path in output_dir.glob("*.jpg"):
        if path.stem.isdigit():
            max_index = max(max_index, int(path.stem))
    return output_dir / f"{max_index + 1:04d}.jpg"


def open_camera(url: str) -> cv2.VideoCapture:
    camera = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return camera


def read_latest(camera: cv2.VideoCapture, drain_frames: int) -> tuple[bool, np.ndarray | None]:
    for _ in range(max(0, drain_frames)):
        if not camera.grab():
            break
    ok, frame = camera.retrieve()
    if not ok or frame is None:
        ok, frame = camera.read()
    return ok, frame


def capture_high_quality(
    capture_url: str,
    args: argparse.Namespace,
    camera_matrix: np.ndarray,
    distortion: np.ndarray,
    new_camera_matrix: np.ndarray,
    capture_camera: cv2.VideoCapture | None = None,
    map_cache: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] | None = None,
) -> tuple[np.ndarray | None, cv2.VideoCapture | None]:
    camera = capture_camera or open_camera(capture_url)
    if not camera.isOpened():
        print("Could not open the high-quality capture stream.", file=sys.stderr)
        if capture_camera is None:
            camera.release()
        return None, capture_camera

    frame = None
    for _ in range(max(1, args.capture_timeout_frames)):
        ok, candidate = read_latest(camera, args.capture_drain_frames)
        if ok and candidate is not None:
            frame = candidate
            break

    if capture_camera is None:
        camera.release()

    if frame is None:
        print("Could not read a high-quality capture frame.", file=sys.stderr)
        return None, capture_camera

    height, width = frame.shape[:2]
    if (width, height) != (args.expected_width, args.expected_height):
        print(
            f"Warning: expected saved image {args.expected_width}x{args.expected_height}, "
            f"but capture stream is {width}x{height}.",
            file=sys.stderr,
        )

    maps = map_cache.get((width, height)) if map_cache is not None else None
    if maps is None:
        maps = cv2.initUndistortRectifyMap(
            camera_matrix,
            distortion,
            None,
            new_camera_matrix,
            (width, height),
            cv2.CV_32FC1,
        )
        if map_cache is not None:
            map_cache[(width, height)] = maps
    map_x, map_y = maps
    undistorted = cv2.remap(
        frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT
    )
    return undistorted, capture_camera


def main() -> int:
    args = parse_args()
    password = args.password or getpass.getpass(
        f"Password for {args.username}@{args.host}: "
    )

    try:
        camera_matrix, distortion, new_camera_matrix = load_calibration(
            args.calibration_path
        )
        preview_url, capture_url = make_stream_urls(args, password)
    except (FileNotFoundError, ValueError, OSError) as error:
        print(error, file=sys.stderr)
        return 1

    os.environ.setdefault(
        "OPENCV_FFMPEG_CAPTURE_OPTIONS",
        "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|max_delay;500000",
    )
    preview_camera = open_camera(preview_url)
    if not preview_camera.isOpened():
        print("Could not open the low-latency preview stream.", file=sys.stderr)
        return 1

    capture_camera = None if args.close_capture_between_shots else open_camera(capture_url)
    if capture_camera is not None and not capture_camera.isOpened():
        capture_camera.release()
        capture_camera = None
        print("Could not keep capture stream open; will open it only when saving.")

    map_cache: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {}
    map_cache[(args.expected_width, args.expected_height)] = cv2.initUndistortRectifyMap(
        camera_matrix,
        distortion,
        None,
        new_camera_matrix,
        (args.expected_width, args.expected_height),
        cv2.CV_32FC1,
    )

    args.output_path.mkdir(parents=True, exist_ok=True)
    window_name = "IP Camera Image Capture"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 720)
    print(f"Preview stream: channel {args.preview_channel} unless URL override is used")
    print(f"Capture stream: channel {args.capture_channel} unless URL override is used")
    print(f"Images will be saved in: {args.output_path.resolve()}")
    if capture_camera is not None:
        print("High-quality capture stream is kept open for faster saves.")
    print("Preview is mirrored. Saved images are not mirrored.")
    print("Focus the preview window. Press Enter to capture; press q or Esc to quit.")
    printed_preview_resolution = False

    try:
        while True:
            ok, preview_frame = read_latest(preview_camera, args.preview_drain_frames)
            if not ok or preview_frame is None:
                print("Failed to read a frame from the preview stream.", file=sys.stderr)
                continue

            if not printed_preview_resolution:
                height, width = preview_frame.shape[:2]
                print(f"Preview frame size: {width}x{height}")
                printed_preview_resolution = True

            preview = (
                cv2.flip(preview_frame, 1)
                if not args.no_mirror_preview
                else preview_frame.copy()
            )
            cv2.putText(
                preview,
                "ENTER: capture high quality    Q/ESC: quit",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow(window_name, preview)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key not in (10, 13):
                continue

            image, capture_camera = capture_high_quality(
                capture_url,
                args,
                camera_matrix,
                distortion,
                new_camera_matrix,
                capture_camera,
                map_cache,
            )
            if image is None:
                continue

            output_file = next_output_path(args.output_path)
            if cv2.imwrite(str(output_file), image):
                print(f"Saved: {output_file.resolve()}")
            else:
                print(f"Failed to save: {output_file}", file=sys.stderr)
    except KeyboardInterrupt:
        print()
    finally:
        preview_camera.release()
        if capture_camera is not None:
            capture_camera.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
