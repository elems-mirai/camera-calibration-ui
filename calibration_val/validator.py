from __future__ import annotations

from dataclasses import dataclass
import os
from typing import List

import numpy as np
import cv2


@dataclass
class PointInput:
    point_id: int
    u: float
    v: float
    expected_x: float
    expected_y: float


@dataclass
class PointResult:
    point_id: int
    u: float
    v: float
    u_undistorted: float        # undistorted pixel coords for reference
    v_undistorted: float
    expected_x: float
    expected_y: float
    predicted_x: float
    predicted_y: float
    error_x: float
    error_y: float
    error_norm: float


class ImgToWorldValidator:
    """Runs image-to-world validation using raw image pixels (K + dist_coeffs)."""

    def __init__(self, camera_dir: str) -> None:
        self.camera_dir = camera_dir
        self._load_camera_data()

    def _load_camera_data(self) -> None:
        needed = {
            "camera_matrix":  "camera_matrix.npy",   # K — raw intrinsics
            "dist_coeffs":    "distortion_coeff.npy",      # distortion coefficients
            "rotation_matrix":"rotation_matrix.npy",
            "tvec":           "tvec.npy",
        }
        missing = [
            os.path.join(self.camera_dir, fn)
            for fn in needed.values()
            if not os.path.exists(os.path.join(self.camera_dir, fn))
        ]
        if missing:
            raise FileNotFoundError(
                "Missing required camera files:\n" + "\n".join(missing)
            )

        camera_matrix   = np.load(os.path.join(self.camera_dir, needed["camera_matrix"]))
        dist_coeffs     = np.load(os.path.join(self.camera_dir, needed["dist_coeffs"]))
        rotation_matrix = np.load(os.path.join(self.camera_dir, needed["rotation_matrix"]))
        tvec            = np.load(os.path.join(self.camera_dir, needed["tvec"]))

        self.camera_matrix     = camera_matrix.astype(np.float64)
        self.dist_coeffs       = dist_coeffs.astype(np.float64)
        self.inv_camera_matrix = np.linalg.inv(self.camera_matrix)
        self.inv_rotation_matrix = np.linalg.inv(rotation_matrix.astype(np.float64))
        self.tvec              = tvec.astype(np.float64)

    def _undistort_pixel(self, u: float, v: float) -> tuple[float, float]:
        """Remove lens distortion from a raw pixel coordinate."""
        pts = np.array([[[u, v]]], dtype=np.float64)
        undistorted = cv2.undistortPoints(
            pts,
            self.camera_matrix,
            self.dist_coeffs,
            P=self.camera_matrix   # keep result in pixel space
        )
        u_u = float(undistorted[0, 0, 0])
        v_u = float(undistorted[0, 0, 1])
        return u_u, v_u

    def _deproject(self, u: float, v: float, scaling_factor: float) -> np.ndarray:
        """Deproject an UNDISTORTED pixel into world space."""
        uv_1 = np.array([[u, v, 1.0]], dtype=np.float64).T
        suv_1 = scaling_factor * uv_1
        xyz_c = self.inv_camera_matrix.dot(suv_1)
        xyz_c = xyz_c - self.tvec
        xyz_w = self.inv_rotation_matrix.dot(xyz_c)
        return xyz_w

    def image_to_world(
        self, u: float, v: float, world_z: float = 0.0
    ) -> tuple[np.ndarray, float, float]:
        """
        Convert a RAW pixel (u, v) to world coordinates.
        Returns (world_xyz, u_undistorted, v_undistorted).
        """
        # Step 1 — undistort the raw pixel first
        u_u, v_u = self._undistort_pixel(u, v)

        # Step 2 — ray-plane intersection using undistorted coords + K
        a_point = self._deproject(u_u, v_u, scaling_factor=0.0)
        b_point = self._deproject(u_u, v_u, scaling_factor=1.0)

        denom = float((b_point[2] - a_point[2]).item())
        if abs(denom) < 1e-9:
            raise ZeroDivisionError(
                f"Cannot intersect ray with z={world_z} plane for pixel ({u}, {v})."
            )

        a_x = float(a_point[0].item())
        a_y = float(a_point[1].item())
        a_z = float(a_point[2].item())
        b_x = float(b_point[0].item())
        b_y = float(b_point[1].item())

        t  = (float(world_z) - a_z) / denom
        xw = t * (b_x - a_x) + a_x
        yw = t * (b_y - a_y) + a_y

        return np.array([xw, yw, float(world_z)], dtype=np.float64), u_u, v_u

    def validate_points(self, points: List[PointInput]) -> List[PointResult]:
        results: List[PointResult] = []
        for point in points:
            predicted, u_u, v_u = self.image_to_world(point.u, point.v, world_z=0.0)
            predicted_x = float(predicted[0])
            predicted_y = float(predicted[1])
            error_x     = point.expected_x - predicted_x
            error_y     = point.expected_y - predicted_y
            error_norm  = float(np.sqrt(error_x**2 + error_y**2))

            results.append(
                PointResult(
                    point_id=point.point_id,
                    u=point.u,
                    v=point.v,
                    u_undistorted=u_u,
                    v_undistorted=v_u,
                    expected_x=point.expected_x,
                    expected_y=point.expected_y,
                    predicted_x=predicted_x,
                    predicted_y=predicted_y,
                    error_x=error_x,
                    error_y=error_y,
                    error_norm=error_norm,
                )
            )
        return results

    def summary(self, results: List[PointResult]) -> dict:
        """Print and return error statistics."""
        errors = [r.error_norm for r in results]
        stats = {
            "mean":   float(np.mean(errors)),
            "std":    float(np.std(errors)),
            "max":    float(np.max(errors)),
            "min":    float(np.min(errors)),
            "median": float(np.median(errors)),
        }
        print("\n=== Validation Summary ===")
        for k, v in stats.items():
            print(f"  {k:>6}: {v:.4f} m")
        print("\n=== Per-Point Results ===")
        print(f"{'ID':>4} {'u':>7} {'v':>7} {'exp_x':>9} {'exp_y':>9} "
              f"{'pred_x':>9} {'pred_y':>9} {'err_x':>8} {'err_y':>8} {'norm':>8}")
        for r in results:
            print(f"{r.point_id:>4} {r.u:>7.1f} {r.v:>7.1f} "
                  f"{r.expected_x:>9.4f} {r.expected_y:>9.4f} "
                  f"{r.predicted_x:>9.4f} {r.predicted_y:>9.4f} "
                  f"{r.error_x:>8.4f} {r.error_y:>8.4f} {r.error_norm:>8.4f}")
        return stats