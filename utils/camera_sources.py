import os
from pathlib import Path
from urllib.parse import quote

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAMERA_FOLDERS = {
    "ip_camera": PROJECT_ROOT / "camera" / "ip_camera",
    "femto_bolt": PROJECT_ROOT / "camera" / "femto_bolt",
}

IP_CAMERA_HOST = os.environ.get("IP_CAMERA_HOST", "192.168.50.45")
IP_CAMERA_USERNAME = os.environ.get("IP_CAMERA_USERNAME", "admin")
IP_CAMERA_STREAM_PATH = os.environ.get(
    "IP_CAMERA_STREAM_PATH", "/Streaming/Channels/101"
)
IP_CAMERA_DRAIN_FRAMES = max(0, int(os.environ.get("IP_CAMERA_DRAIN_FRAMES", "3")))
FEMTO_COLOR_TOPIC = os.environ.get("FEMTO_COLOR_TOPIC", "/camera/color/image_raw")


def default_camera_folder(source_key):
    return str(DEFAULT_CAMERA_FOLDERS.get(source_key, PROJECT_ROOT / "camera"))


def ensure_camera_folder(base_dir):
    os.makedirs(os.path.join(base_dir, "intrinsic_images"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "extrinsic_images"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "camera_data"), exist_ok=True)


def build_ip_stream_url(password):
    host = IP_CAMERA_HOST.removeprefix("http://").removeprefix("https://").rstrip("/")
    auth = f"{quote(IP_CAMERA_USERNAME, safe='')}:{quote(password, safe='')}"
    return f"rtsp://{auth}@{host}:554{IP_CAMERA_STREAM_PATH}"


class IPCameraStream:
    def __init__(self, password):
        self.url = build_ip_stream_url(password)
        os.environ.setdefault(
            "OPENCV_FFMPEG_CAPTURE_OPTIONS",
            "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|max_delay;500000",
        )
        self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self.cap.isOpened():
            self.cap.release()

    def isOpened(self):
        return self.cap.isOpened()

    def read(self):
        for _ in range(IP_CAMERA_DRAIN_FRAMES):
            if not self.cap.grab():
                break
        return self.cap.retrieve()

    def release(self):
        self.cap.release()


def _ros_image_to_bgr(msg):
    height = int(msg.height)
    width = int(msg.width)
    encoding = msg.encoding.lower()

    if encoding in ("bgr8", "rgb8"):
        channels = 3
    elif encoding in ("bgra8", "rgba8"):
        channels = 4
    elif encoding in ("mono8", "8uc1"):
        channels = 1
    else:
        raise RuntimeError(f"Unsupported ROS image encoding: {msg.encoding}")

    data = np.frombuffer(msg.data, dtype=np.uint8)
    if channels == 1:
        image = data.reshape((height, int(msg.step)))[:, :width]
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    row_width = width * channels
    image = data.reshape((height, int(msg.step)))[:, :row_width]
    image = image.reshape((height, width, channels))

    if encoding == "rgb8":
        return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    if encoding == "rgba8":
        return cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
    if encoding == "bgra8":
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image.copy()


class FemtoRos1Stream:
    def __init__(self):
        try:
            import rospy
            from sensor_msgs.msg import Image
        except ImportError as error:
            raise RuntimeError(
                "ROS 1 packages are not available."
            ) from error

        self.rospy = rospy
        self.latest_frame = None

        if not rospy.core.is_initialized():
            rospy.init_node(
                "camera_calibration_ui",
                anonymous=True,
                disable_signals=True,
            )

        self.subscriber = rospy.Subscriber(
            FEMTO_COLOR_TOPIC,
            Image,
            self._on_image,
            queue_size=1,
            buff_size=2**24,
        )

    def _on_image(self, msg):
        try:
            self.latest_frame = _ros_image_to_bgr(msg)
        except Exception as error:
            print(f"[Femto] Failed to convert ROS image: {error}")

    def isOpened(self):
        return self.subscriber is not None

    def read(self):
        if self.latest_frame is None:
            return False, None
        return True, self.latest_frame.copy()

    def release(self):
        if self.subscriber is not None:
            self.subscriber.unregister()
            self.subscriber = None


class FemtoRos2Stream:
    def __init__(self):
        try:
            import rclpy
            from rclpy.qos import qos_profile_sensor_data
            from sensor_msgs.msg import Image
        except ImportError as error:
            raise RuntimeError(
                "ROS 2 packages are not available. Source /opt/ros/jazzy/setup.bash "
                "and make sure Python can import rclpy and sensor_msgs."
            ) from error

        self.rclpy = rclpy
        self.latest_frame = None
        self.node = None
        self.subscription = None

        if not rclpy.ok():
            rclpy.init(args=None)

        self.node = rclpy.create_node("camera_calibration_ui")
        self.subscription = self.node.create_subscription(
            Image,
            FEMTO_COLOR_TOPIC,
            self._on_image,
            qos_profile_sensor_data,
        )

    def _on_image(self, msg):
        try:
            self.latest_frame = _ros_image_to_bgr(msg)
        except Exception as error:
            print(f"[Femto] Failed to convert ROS 2 image: {error}")

    def isOpened(self):
        return self.node is not None and self.subscription is not None

    def read(self):
        if self.node is not None:
            self.rclpy.spin_once(self.node, timeout_sec=0.01)
        if self.latest_frame is None:
            return False, None
        return True, self.latest_frame.copy()

    def release(self):
        if self.node is not None:
            self.node.destroy_node()
            self.node = None
            self.subscription = None


class FemtoRosStream:
    def __new__(cls):
        try:
            return FemtoRos1Stream()
        except RuntimeError as ros1_error:
            try:
                return FemtoRos2Stream()
            except RuntimeError as ros2_error:
                raise RuntimeError(
                    "Femto Bolt capture needs ROS image support.\n"
                    f"ROS 1 error: {ros1_error}\n"
                    f"ROS 2 error: {ros2_error}"
                ) from ros2_error


def create_camera_source(source_key, password=None):
    if source_key == "ip_camera":
        if not password:
            raise RuntimeError("IP camera password is required.")
        return IPCameraStream(password)
    if source_key == "femto_bolt":
        return FemtoRosStream()
    raise RuntimeError(f"Unsupported camera source: {source_key}")
