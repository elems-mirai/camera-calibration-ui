# ui/clickable_label.py
from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import Qt, QPoint, QTimer, QRect
from PyQt5.QtGui import QPainter, QPixmap, QPen, QFont
from PyQt5.QtGui import QColor
import math

class ClickableLabel(QLabel):
    """Optimized QLabel:
    - Left-click → select point
    - Right-click → drag/pan
    - Wheel → zoom
    - Caches scaled pixmap and throttles repaint
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(64, 64)

        self._click_callback = None
        self._points = {}  # {idx: (x, y)}

        self._interaction_enabled = True

        # pixmap caches
        self._original_pixmap = None
        self._cached_scaled_pixmap = None
        self._cached_zoom = None

        # view state
        self._zoom_factor = 1.0
        self._pan_offset = QPoint(0, 0)
        self._viewport_padding = 8
        self._dragging = False
        self._last_mouse_pos = None
        self._repaint_pending = False

        # drawing config
        self._background_color = QColor("#f6f7f8")
        self._point_radius = 4
        self._font = QFont()
        self._font.setPointSize(9)
        self._pen_point = QPen(Qt.red)
        self._pen_point.setWidth(2)
        self._pen_text = QPen(Qt.white)

    # ---------------------------------------------------------
    # Public interface
    # ---------------------------------------------------------
    def set_click_callback(self, fn):
        self._click_callback = fn

    def add_point(self, idx, x, y):
        self._points[int(idx)] = (float(x), float(y))
        self.repaint()

    def clear_points(self):
        self._points.clear()
        self.repaint()

    def reset_view(self):
        self._fit_pixmap_to_label()
        self._cached_scaled_pixmap = None
        self._cached_zoom = None
        self.repaint()

    def setPixmap(self, pixmap: QPixmap):
        self._original_pixmap = pixmap
        self._fit_pixmap_to_label()
        self._cached_scaled_pixmap = None
        self._cached_zoom = None
        super().setPixmap(pixmap)
        self.repaint()

    # ---------------------------------------------------------
    # Painting (optimized)
    # ---------------------------------------------------------
    def paintEvent(self, event):
        if self._original_pixmap is None or self._original_pixmap.isNull():
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.fillRect(self.rect(), self._background_color)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # --- Cached scaled pixmap ---
        if self._cached_zoom != self._zoom_factor or self._cached_scaled_pixmap is None:
            scaled_size = self._original_pixmap.size() * self._zoom_factor
            self._cached_scaled_pixmap = self._original_pixmap.scaled(
                scaled_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._cached_zoom = self._zoom_factor

        painter.drawPixmap(self._pan_offset, self._cached_scaled_pixmap)

        # --- Define P1-P6 colors ---
        colors = [
            QColor(255, 0, 0),     # P1 - Red
            QColor(0, 255, 0),     # P2 - Green
            QColor(0, 0, 255),     # P3 - Blue
            QColor(204, 102, 0),   # P4 - Orange
            QColor(255, 0, 255),   # P5 - Magenta
            QColor(0, 140, 160),   # P6 - Teal
        ]

        # --- Draw filled points ---
        painter.setFont(self._font)
        for idx, (x, y) in self._points.items():
            sx = int(x * self._zoom_factor) + self._pan_offset.x()
            sy = int(y * self._zoom_factor) + self._pan_offset.y()

            color = colors[(idx - 1) % len(colors)]
            painter.setBrush(color)
            painter.setPen(Qt.black)  # black border for contrast
            painter.drawEllipse(QRect(sx - 5, sy - 5, 10, 10))  # filled circle

            # --- Label text (white for visibility) ---
            painter.setPen(Qt.white)
            painter.drawText(sx + 8, sy - 6, f"P{idx}")

        painter.end()


    # ---------------------------------------------------------
    # Mouse interaction
    # ---------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._interaction_enabled:
            img_xy = self._to_image_coords(event.pos())
            if img_xy and self._click_callback:
                x, y = img_xy
                self._click_callback(int(x), int(y))
        elif event.button() == Qt.RightButton and self._interaction_enabled:
            self._last_mouse_pos = event.pos()
            self._dragging = True
        super().mousePressEvent(event)


    def mouseMoveEvent(self, event):
        if not getattr(self, "_interaction_enabled", True):
            return
        if self._dragging and self._last_mouse_pos is not None:
            delta = event.pos() - self._last_mouse_pos
            self._pan_offset += delta
            self._last_mouse_pos = event.pos()
            self._throttled_repaint(15)
        super().mouseMoveEvent(event)


    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            self._dragging = False
            self._last_mouse_pos = None
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if not getattr(self, "_interaction_enabled", True):
            return  # 🚫 ignore zoom events
        if self._original_pixmap is None:
            return
        delta_steps = event.angleDelta().y() / 120.0
        if delta_steps == 0:
            return

        old_zoom = self._zoom_factor
        new_zoom = max(0.1, min(10.0, old_zoom * (1.0 + 0.1 * delta_steps)))
        if math.isclose(new_zoom, old_zoom, rel_tol=1e-3):
            return

        cursor_pos = event.pos()
        before = self._to_image_coords(cursor_pos)
        self._zoom_factor = new_zoom
        self._cached_zoom = None

        if before:
            bx, by = before
            after_screen = self._to_screen_coords((bx, by))
            if after_screen:
                ax, ay = after_screen
                delta = cursor_pos - QPoint(int(ax), int(ay))
                self._pan_offset += delta

        self.repaint()

    # ---------------------------------------------------------
    # Helper methods
    # ---------------------------------------------------------
    def _to_image_coords(self, screen_pt: QPoint):
        if self._original_pixmap is None:
            return None
        px = (screen_pt.x() - self._pan_offset.x()) / self._zoom_factor
        py = (screen_pt.y() - self._pan_offset.y()) / self._zoom_factor
        if 0 <= px < self._original_pixmap.width() and 0 <= py < self._original_pixmap.height():
            return (px, py)
        return None

    def _to_screen_coords(self, img_xy):
        if img_xy is None:
            return None
        x, y = img_xy
        sx = int(x * self._zoom_factor) + self._pan_offset.x()
        sy = int(y * self._zoom_factor) + self._pan_offset.y()
        return (sx, sy)

    def _fit_pixmap_to_label(self):
        if self._original_pixmap is None or self._original_pixmap.isNull():
            self._zoom_factor = 1.0
            self._pan_offset = QPoint(0, 0)
            return

        pix_w = self._original_pixmap.width()
        pix_h = self._original_pixmap.height()
        label_w = max(1, self.width())
        label_h = max(1, self.height())
        usable_w = max(1, label_w - 2 * self._viewport_padding)
        usable_h = max(1, label_h - 2 * self._viewport_padding)

        self._zoom_factor = min(usable_w / pix_w, usable_h / pix_h)
        scaled_w = int(pix_w * self._zoom_factor)
        scaled_h = int(pix_h * self._zoom_factor)
        self._pan_offset = QPoint(
            max(self._viewport_padding, (label_w - scaled_w) // 2),
            max(self._viewport_padding, (label_h - scaled_h) // 2),
        )

    def _throttled_repaint(self, ms: int):
        if not self._repaint_pending:
            self._repaint_pending = True
            QTimer.singleShot(ms, self._do_repaint)

    def _do_repaint(self):
        self._repaint_pending = False
        self.repaint()

    def queue_repaint(self):
        # immediate repaint is fine for discrete actions
        self.repaint()
