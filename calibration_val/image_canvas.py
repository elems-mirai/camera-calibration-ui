from __future__ import annotations

from typing import Dict, Optional, Tuple

from PyQt5.QtCore import QPoint, QPointF, QRect, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QLabel


class ImageCanvas(QLabel):
    """Large preview widget with Photoshop-like wheel zoom and middle-button pan."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(760, 760)
        self.setMouseTracking(True)

        self._original_pixmap: Optional[QPixmap] = None
        self._scaled_pixmap: Optional[QPixmap] = None
        self._base_scale: float = 1.0
        self._zoom_factor: float = 1.0
        self._scale: float = 1.0
        self._offset = QPointF(0.0, 0.0)
        self._active_point_id: Optional[int] = None
        self._points: Dict[int, Tuple[float, float]] = {}
        self._click_callback = None
        self._is_panning = False
        self._last_pan_pos: Optional[QPoint] = None

        self._label_font = QFont("Segoe UI", 10)
        self._outline_pen = QPen(Qt.black, 2)

    def set_click_callback(self, callback) -> None:
        self._click_callback = callback

    def load_pixmap(self, pixmap: QPixmap) -> None:
        self._original_pixmap = pixmap
        self._zoom_factor = 1.0
        self._rebuild_scaled_pixmap()
        self.update()

    def clear_canvas(self) -> None:
        self._original_pixmap = None
        self._scaled_pixmap = None
        self._points.clear()
        self._active_point_id = None
        self._zoom_factor = 1.0
        self._offset = QPointF(0.0, 0.0)
        self._is_panning = False
        self._last_pan_pos = None
        self.update()

    def set_active_point(self, point_id: Optional[int]) -> None:
        self._active_point_id = point_id
        self.update()

    def set_point(self, point_id: int, u: float, v: float) -> None:
        self._points[point_id] = (u, v)
        self.update()

    def remove_point(self, point_id: int) -> None:
        if point_id in self._points:
            del self._points[point_id]
            self.update()

    def reset_points(self) -> None:
        self._points.clear()
        self.update()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._rebuild_scaled_pixmap()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if self._original_pixmap is None:
            return super().mousePressEvent(event)

        if event.button() == Qt.MiddleButton:
            self._is_panning = True
            self._last_pan_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.LeftButton:
            image_xy = self._to_image_coords(event.pos())
            if image_xy is not None and self._click_callback is not None:
                self._click_callback(image_xy[0], image_xy[1])
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._is_panning and self._last_pan_pos is not None:
            delta = event.pos() - self._last_pan_pos
            self._offset += QPointF(float(delta.x()), float(delta.y()))
            self._last_pan_pos = event.pos()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MiddleButton:
            self._is_panning = False
            self._last_pan_pos = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if self._original_pixmap is None:
            return super().wheelEvent(event)

        image_xy = self._to_image_coords(event.pos())
        if image_xy is None:
            return super().wheelEvent(event)

        delta_steps = event.angleDelta().y() / 120.0
        if delta_steps == 0:
            return

        old_zoom = self._zoom_factor
        zoom_multiplier = 1.15 ** delta_steps
        new_zoom = max(0.2, min(20.0, old_zoom * zoom_multiplier))
        if abs(new_zoom - old_zoom) < 1e-6:
            return

        self._zoom_factor = new_zoom
        self._rebuild_scaled_pixmap(anchor_widget_pos=event.pos(), anchor_image_pos=image_xy)
        self.update()
        event.accept()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QColor("#eef2eb"))

        if self._scaled_pixmap is None:
            painter.setPen(QColor("#445448"))
            painter.setFont(self._label_font)
            painter.drawText(self.rect(), Qt.AlignCenter, "No image selected")
            painter.end()
            return

        painter.drawPixmap(self._offset.toPoint(), self._scaled_pixmap)
        painter.setFont(self._label_font)

        for point_id, (u, v) in self._points.items():
            sx, sy = self._to_screen_coords(u, v)
            is_active = point_id == self._active_point_id
            radius = 7 if is_active else 5
            fill = QColor("#d12f2f") if is_active else QColor("#2f6fb3")
            painter.setPen(self._outline_pen)
            painter.setBrush(fill)
            painter.drawEllipse(QRect(sx - radius, sy - radius, radius * 2, radius * 2))
            painter.setPen(Qt.white)
            painter.drawText(sx + 10, sy - 8, f"P{point_id} ({u:.1f}, {v:.1f})")

        painter.end()

    def _rebuild_scaled_pixmap(
        self,
        anchor_widget_pos: Optional[QPoint] = None,
        anchor_image_pos: Optional[Tuple[float, float]] = None,
    ) -> None:
        if self._original_pixmap is None or self._original_pixmap.isNull():
            self._scaled_pixmap = None
            self._base_scale = 1.0
            self._scale = 1.0
            self._offset = QPointF(0.0, 0.0)
            return

        base_fit = self._original_pixmap.scaled(
            self.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._base_scale = base_fit.width() / self._original_pixmap.width()
        self._scale = self._base_scale * self._zoom_factor

        scaled_width = max(1, int(round(self._original_pixmap.width() * self._scale)))
        scaled_height = max(1, int(round(self._original_pixmap.height() * self._scale)))
        self._scaled_pixmap = self._original_pixmap.scaled(
            scaled_width,
            scaled_height,
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation,
        )

        if anchor_widget_pos is not None and anchor_image_pos is not None:
            self._offset = QPointF(
                float(anchor_widget_pos.x()) - anchor_image_pos[0] * self._scale,
                float(anchor_widget_pos.y()) - anchor_image_pos[1] * self._scale,
            )
        elif self._zoom_factor == 1.0:
            self._offset = QPointF(
                float((self.width() - scaled_width) / 2.0),
                float((self.height() - scaled_height) / 2.0),
            )

        self._clamp_offset()

    def _clamp_offset(self) -> None:
        if self._scaled_pixmap is None:
            return

        if self._scaled_pixmap.width() <= self.width():
            x = float((self.width() - self._scaled_pixmap.width()) / 2.0)
        else:
            min_x = float(self.width() - self._scaled_pixmap.width())
            max_x = 0.0
            x = min(max(self._offset.x(), min_x), max_x)

        if self._scaled_pixmap.height() <= self.height():
            y = float((self.height() - self._scaled_pixmap.height()) / 2.0)
        else:
            min_y = float(self.height() - self._scaled_pixmap.height())
            max_y = 0.0
            y = min(max(self._offset.y(), min_y), max_y)

        self._offset = QPointF(x, y)

    def _to_image_coords(self, pos: QPoint) -> Optional[Tuple[float, float]]:
        if self._original_pixmap is None or self._scaled_pixmap is None:
            return None

        x = pos.x() - self._offset.x()
        y = pos.y() - self._offset.y()
        if x < 0 or y < 0 or x >= self._scaled_pixmap.width() or y >= self._scaled_pixmap.height():
            return None
        if self._scale == 0:
            return None
        return (x / self._scale, y / self._scale)

    def _to_screen_coords(self, u: float, v: float) -> Tuple[int, int]:
        sx = int(round(u * self._scale + self._offset.x()))
        sy = int(round(v * self._scale + self._offset.y()))
        return sx, sy
