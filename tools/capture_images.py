#!/usr/bin/env python3
"""Interactively capture JPEG images from an IP camera."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import cv2


DEFAULT_HOST = "192.168.50.45"
DEFAULT_USERNAME = "admin"
DEFAULT_SAVE_PATH = Path(__file__).resolve().parents[1] / "Cameras" / "ip_camera" / "intrinsic_images"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview an IP camera; press Enter to capture and q to quit."
    )
    parser.add_argument(
        "save_path",
        nargs="?",
        type=Path,
        default=DEFAULT_SAVE_PATH,
        help=f"directory in which to save images (default: {DEFAULT_SAVE_PATH})",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="camera host or web URL")
    parser.add_argument("--username", default=DEFAULT_USERNAME, help="camera username")
    parser.add_argument(
        "--password",
        default=os.environ.get("CAMERA_PASSWORD"),
        help="camera password (prefer the CAMERA_PASSWORD environment variable)",
    )
    parser.add_argument(
        "--stream-url",
        help=(
            "complete RTSP stream URL; defaults to "
            "rtsp://HOST:554/Streaming/Channels/101"
        ),
    )
    parser.add_argument("--prefix", default="capture", help="saved filename prefix")
    return parser.parse_args()


def make_stream_url(args: argparse.Namespace, password: str) -> str:
    if args.stream_url:
        parts = urlsplit(args.stream_url)
        if parts.username is not None:
            return args.stream_url
        host = parts.hostname or parts.netloc
        port = f":{parts.port}" if parts.port else ""
        auth = f"{quote(args.username, safe='')}:{quote(password, safe='')}@"
        return urlunsplit((parts.scheme, f"{auth}{host}{port}", parts.path, parts.query, ""))

    host = args.host.removeprefix("http://").removeprefix("https://").rstrip("/")
    auth = f"{quote(args.username, safe='')}:{quote(password, safe='')}"
    return f"rtsp://{auth}@{host}:554/Streaming/Channels/101"


def main() -> int:
    args = parse_args()
    password = args.password or getpass.getpass(
        f"Password for {args.username}@{args.host}: "
    )
    stream_url = make_stream_url(args, password)

    args.save_path.mkdir(parents=True, exist_ok=True)
    camera = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
    if not camera.isOpened():
        print(
            "Could not open the camera stream. Check the credentials and RTSP endpoint; "
            "use --stream-url if necessary.",
            file=sys.stderr,
        )
        return 1

    print(f"Connected. Images will be saved in: {args.save_path.resolve()}")
    print("Focus the preview window. Press Enter to capture; press q or Esc to quit.")

    window_name = "IP Camera Capture"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 720)

    try:
        while True:
            ok, frame = camera.read()
            if not ok or frame is None:
                print("Failed to read a frame from the camera.", file=sys.stderr)
                continue

            preview = frame.copy()
            cv2.putText(
                preview,
                "ENTER: capture    Q/ESC: quit",
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

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            milliseconds = int(time.time_ns() / 1_000_000) % 1000
            output = args.save_path / f"{args.prefix}_{timestamp}_{milliseconds:03d}.jpg"
            if cv2.imwrite(str(output), frame):
                print(f"Saved: {output.resolve()}")
            else:
                print(f"Failed to save: {output}", file=sys.stderr)
    except KeyboardInterrupt:
        print()
    finally:
        camera.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
