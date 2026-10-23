# -*- coding: utf-8 -*-
"""通用 UI 组件：导航、分段控件、开关、统计卡、摄像头画面、日志项。"""

from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..theme import (
    ACCENT,
    ACCENT2,
    AMBER,
    BG2,
    BORDER,
    BORDER_SOFT,
    CARD,
    CARD2,
    FAINT,
    GREEN,
    MUTED,
    PANEL,
    RED,
    TEXT,
)
from .icons import make_icon, make_pixmap


def ui_font(size: int, bold: bool = False) -> QFont:
    font = QFont("Microsoft YaHei UI")
    font.setPixelSize(int(size))
    font.setBold(bold)
    return font


def bgr_to_qimage(bgr: np.ndarray) -> QImage:
    bgr = np.ascontiguousarray(bgr)
    h, w = bgr.shape[:2]
    return QImage(
        bgr.data, w, h, bgr.strides[0], QImage.Format.Format_BGR888
    ).copy()


def color_alpha(hex_color: str, alpha: float) -> QColor:
    c = QColor(hex_color)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


class Card(QFrame):
    def __init__(self, parent=None, object_name: str = "Card"):
        super().__init__(parent)
        self.setObjectName(object_name)


class NavButton(QPushButton):
    def __init__(self, icon_name: str, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setFixedHeight(42)
        self.setCursor(Qt.PointingHandCursor)
        self.setIcon(make_icon(icon_name, MUTED, 20))
        self.setIconSize(QSize(20, 20))
        self._icon_name = icon_name
        self.toggled.connect(self._sync_icon)

    def _sync_icon(self, checked: bool) -> None:
        self.setIcon(make_icon(self._icon_name, ACCENT if checked else MUTED, 20))


class SegmentedControl(QWidget):
    changed = Signal(int)

    def __init__(self, labels: list[str], current: int = 0, parent=None):
        super().__init__(parent)
        self.setObjectName("Segmented")
        self.setFixedHeight(32)
        self.buttons: list[QPushButton] = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        width = 38 if len(labels) >= 4 else 58
        for i, label in enumerate(labels):
            btn = QPushButton(label)
            btn.setObjectName("SegBtn")
            btn.setCheckable(True)
            btn.setFixedSize(width, 24)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, idx=i: self.setCurrent(idx, True))
            layout.addWidget(btn)
            self.buttons.append(btn)
        self.setFixedWidth(8 + len(labels) * width + (len(labels) - 1) * 4 + 8)
        self.setCurrent(current, False)

    def setCurrent(self, index: int, emit: bool = True) -> None:
        index = max(0, min(len(self.buttons) - 1, int(index)))
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        if emit:
            self.changed.emit(index)

    def current(self) -> int:
        for i, btn in enumerate(self.buttons):
            if btn.isChecked():
                return i
        return 0


class ToggleSwitch(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(38, 22)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        rect = QRectF(1, 2, 36, 18)
        p.setBrush(QColor(ACCENT) if self.isChecked() else QColor("#1C2A40"))
        p.drawRoundedRect(rect, 9, 9)
        p.setBrush(QColor("#06231D") if self.isChecked() else QColor(MUTED))
        x = 20 if self.isChecked() else 3
        p.drawEllipse(QRectF(x, 4, 14, 14))
        p.end()


class IconButton(QPushButton):
    def __init__(self, icon_name: str, tooltip: str = "", size: int = 32, parent=None):
        super().__init__(parent)
        self.setObjectName("IconButton")
        self.setFixedSize(size, size)
        self.setIcon(make_icon(icon_name, MUTED, max(16, size - 12)))
        self.setIconSize(QSize(max(16, size - 12), max(16, size - 12)))
        self.setCursor(Qt.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)


class IconBadge(QWidget):
    def __init__(self, icon_name: str, color: str = ACCENT, size: int = 34, parent=None):
        super().__init__(parent)
        self._pm = make_pixmap(icon_name, color, 18)
        self._color = QColor(color)
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        c = QColor(self._color)
        c.setAlphaF(0.13)
        p.setBrush(c)
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 9, 9)
        p.drawPixmap(
            (self.width() - self._pm.width()) // 2,
            (self.height() - self._pm.height()) // 2,
            self._pm,
        )
        p.end()


class Sparkline(QWidget):
    def __init__(self, values: list[float], color: str = ACCENT, parent=None):
        super().__init__(parent)
        self.values = values or [0.2] * 12
        self.color = QColor(color)
        self.setMinimumHeight(38)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        n = len(self.values)
        if not n:
            return
        maxv = max(self.values) or 1.0
        gap = 3
        bw = max(2.0, (self.width() - gap * (n - 1)) / n)
        for i, value in enumerate(self.values):
            h = max(3.0, (self.height() - 4) * value / maxv)
            c = QColor(self.color)
            c.setAlphaF(0.30 + 0.55 * i / max(1, n - 1))
            p.setBrush(c)
            x = i * (bw + gap)
            p.drawRoundedRect(QRectF(x, self.height() - h, bw, h), 1.5, 1.5)
        p.end()


class StatCard(QFrame):
    def __init__(self, title: str, value: str, note: str, icon: str,
                 color: str = ACCENT, kind: str = "spark", parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setFixedHeight(148)
        self._title = title
        self._color = color
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(IconBadge(icon, color, 34))
        title_label = QLabel(title)
        title_label.setObjectName("Muted")
        top.addWidget(title_label)
        top.addStretch(1)
        layout.addLayout(top)
        layout.addSpacing(6)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("Value")
        layout.addWidget(self.value_label)

        self.note_label = QLabel(note)
        self.note_label.setObjectName("Good")
        self.note_label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 600;")
        layout.addWidget(self.note_label)
        layout.addStretch(1)

        self.extra = None
        if kind == "spark":
            self.extra = Sparkline([10, 16, 12, 21, 18, 27, 23, 31, 26, 35, 30, 38], color)
        elif kind == "progress":
            from PySide6.QtWidgets import QProgressBar

            self.extra = QProgressBar()
            self.extra.setRange(0, 1000)
            self.extra.setValue(982)
            self.extra.setTextVisible(False)
            self.extra.setFixedHeight(6)
        elif kind == "dots":
            self.extra = DotsWidget(color)
        if self.extra is not None:
            layout.addWidget(self.extra)

    def set_value(self, text: str) -> None:
        self.value_label.setText(text)

    def set_note(self, text: str, color: Optional[str] = None) -> None:
        self.note_label.setText(text)
        if color:
            self.note_label.setStyleSheet(
                f"color: {color}; font-size: 11px; font-weight: 600;"
            )

    def set_progress(self, value: float) -> None:
        if hasattr(self.extra, "setValue"):
            self.extra.setValue(int(max(0, min(1, value)) * 1000))


class DotsWidget(QWidget):
    def __init__(self, color: str = GREEN, count: int = 4, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.count = count
        self.setFixedHeight(14)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_count(self, count: int) -> None:
        self.count = max(0, count)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(self.color)
        for i in range(self.count):
            p.drawEllipse(QRectF(self.width() - 8 - (self.count - 1 - i) * 16, 3, 8, 8))
        p.end()


class Thumb(QWidget):
    def __init__(self, image: Optional[QImage] = None, w: int = 76, h: int = 34, parent=None):
        super().__init__(parent)
        self._image = image
        self.setFixedSize(w, h)

    def set_image(self, image: QImage) -> None:
        self._image = image
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 5, 5)
        p.setClipPath(path)
        p.fillPath(path, QColor(BG2))
        if self._image is not None and not self._image.isNull():
            pm = QPixmap.fromImage(self._image)
            scaled = pm.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            x = (self.width() - scaled.width()) / 2
            y = (self.height() - scaled.height()) / 2
            p.drawPixmap(QPointF(x, y), scaled)
        p.setClipping(False)
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawPath(path)
        p.end()


class PlateLogItem(QFrame):
    def __init__(self, plate: str, cam_name: str, time_text: str, conf: float,
                 thumb: Optional[QImage] = None, parent=None):
        super().__init__(parent)
        self.setObjectName("SubCard")
        self.setFixedHeight(84)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 12, 10)
        layout.setSpacing(10)

        layout.addWidget(Thumb(thumb, 76, 34), 0, Qt.AlignVCenter)

        middle = QVBoxLayout()
        middle.setSpacing(1)
        plate_label = QLabel(plate)
        plate_label.setStyleSheet(
            f"color: {GREEN}; font-size: 14px; font-weight: 700;"
        )
        middle.addWidget(plate_label)
        sub = QLabel(cam_name)
        sub.setObjectName("Muted")
        sub.setStyleSheet("font-size: 11px;")
        middle.addWidget(sub)
        t = QLabel(time_text)
        t.setObjectName("Faint")
        t.setStyleSheet("font-size: 10px;")
        middle.addWidget(t)
        layout.addLayout(middle, 1)

        right = QVBoxLayout()
        right.setSpacing(2)
        conf_label = QLabel(f"{conf * 100:.1f}%")
        conf_label.setStyleSheet(
            f"color: {GREEN}; font-size: 11px; font-weight: 600;"
        )
        conf_label.setAlignment(Qt.AlignRight)
        right.addWidget(conf_label)
        right.addStretch(1)
        saved = QLabel("已保存")
        saved.setObjectName("Faint")
        saved.setStyleSheet("font-size: 9px;")
        saved.setAlignment(Qt.AlignRight)
        right.addWidget(saved)
        layout.addLayout(right)


class CameraTile(QWidget):
    add_requested = Signal()
    reconnect_requested = Signal(str)

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.cam_id = ""
        self.cam_name = ""
        self.kind = ""
        self.configured = False
        self.online = False
        self.status = "未连接"
        self.fps = 0.0
        self._image: Optional[QImage] = None
        self._detections: list = []
        self._frame_size = (0, 0)
        self.setMinimumSize(260, 160)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)

    def set_camera(self, cam_id: str, name: str, kind: str) -> None:
        self.cam_id = cam_id
        self.cam_name = name
        self.kind = kind
        self.configured = True
        self.update()

    def clear_camera(self) -> None:
        self.cam_id = ""
        self.cam_name = ""
        self.kind = ""
        self.configured = False
        self.online = False
        self.status = "未连接"
        self._image = None
        self._detections = []
        self.setCursor(Qt.PointingHandCursor)
        self.update()

    def set_placeholder(self) -> None:
        self.clear_camera()

    def set_frame(self, image: QImage) -> None:
        self._image = image
        self._frame_size = (image.width(), image.height())
        self.update()

    def set_detections(self, detections: list) -> None:
        self._detections = detections or []
        self.update()

    def set_status(self, online: bool, message: str) -> None:
        self.online = online
        self.status = message
        self.setCursor(
            Qt.ArrowCursor if online or not self.configured else Qt.PointingHandCursor
        )
        self.update()

    def set_fps(self, fps: float) -> None:
        self.fps = fps
        self.update()

    def _font(self, base: int, bold: bool = False) -> QFont:
        scale = max(0.9, min(2.0, self.height() / 244.0))
        return ui_font(int(base * scale), bold)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
        p.setClipPath(path)
        p.fillPath(path, QColor(BG2))

        if self._image is not None and not self._image.isNull():
            self._paint_frame(p, rect)
        elif self.configured:
            self._paint_offline(p, rect)
        else:
            self._paint_placeholder(p, rect)

        if self._image is not None and self.configured:
            self._paint_header(p, rect)
            self._paint_detections(p, rect)
            self._paint_footer(p, rect)

        p.setClipping(False)
        p.setPen(QPen(QColor(BORDER_SOFT), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.end()

    def _paint_frame(self, p: QPainter, rect: QRectF) -> None:
        pm = QPixmap.fromImage(self._image)
        iw, ih = self._image.width(), self._image.height()
        if iw <= 0 or ih <= 0:
            return
        scale = max(rect.width() / iw, rect.height() / ih)
        dw, dh = iw * scale, ih * scale
        target = QRectF(
            rect.center().x() - dw / 2, rect.center().y() - dh / 2, dw, dh
        )
        p.drawPixmap(target, pm, QRectF(0, 0, iw, ih))
        self._image_rect = target

        top = QLinearGradient(0, 0, 0, 86)
        top.setColorAt(0, QColor(2, 6, 12, 190))
        top.setColorAt(1, QColor(2, 6, 12, 0))
        p.fillRect(QRectF(0, 0, rect.width(), 86), top)
        bottom = QLinearGradient(0, rect.height() - 110, 0, rect.height())
        bottom.setColorAt(0, QColor(2, 6, 12, 0))
        bottom.setColorAt(1, QColor(2, 6, 12, 225))
        p.fillRect(QRectF(0, rect.height() - 110, rect.width(), 110), bottom)

    def _paint_header(self, p: QPainter, rect: QRectF) -> None:
        color = QColor(GREEN) if self.online else QColor(RED)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawEllipse(QPointF(17, 19), 3.5, 3.5)

        f = self._font(10, True)
        p.setFont(f)
        p.setPen(QColor(TEXT))
        name = self.cam_name or "摄像头"
        p.drawText(QPointF(28, 23), name)
        fm = QFontMetrics(f)
        name_w = fm.horizontalAdvance(name)

        if self.kind:
            badge = "USB" if self.kind == "usb" else "RTSP"
            badge_color = QColor(ACCENT2 if self.kind == "usb" else "#A78BFA")
            bw = 36 if badge == "USB" else 44
            bx = 28 + name_w + 8
            p.setPen(Qt.NoPen)
            bg = QColor(badge_color)
            bg.setAlphaF(0.15)
            p.setBrush(bg)
            p.drawRoundedRect(QRectF(bx, 11, bw, 17), 8, 8)
            p.setPen(badge_color)
            p.setFont(self._font(8, True))
            p.drawText(QRectF(bx, 11, bw, 17), Qt.AlignCenter, badge)

        fps_text = f"{self.fps:.0f} FPS"
        p.setFont(self._font(8.5, True))
        fm = QFontMetrics(p.font())
        pw = fm.horizontalAdvance(fps_text) + 18
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(2, 8, 15, 170))
        p.drawRoundedRect(QRectF(rect.width() - 14 - pw, 11, pw, 19), 9, 9)
        p.setPen(QColor(210, 228, 246))
        p.drawText(QRectF(rect.width() - 14 - pw, 11, pw, 19), Qt.AlignCenter, fps_text)

    def _paint_detections(self, p: QPainter, rect: QRectF) -> None:
        target: QRectF = getattr(self, "_image_rect", rect)
        iw, ih = self._frame_size
        if iw <= 0 or ih <= 0:
            return
        sx = target.width() / iw
        sy = target.height() / ih
        for det in self._detections:
            x1, y1, x2, y2 = det.box
            box = QRectF(target.x() + x1 * sx, target.y() + y1 * sy,
                         (x2 - x1) * sx, (y2 - y1) * sy)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(ACCENT), 2))
            p.drawRoundedRect(box, 3, 3)
            if det.text:
                f = self._font(9, True)
                p.setFont(f)
                fm = QFontMetrics(f)
                tw = fm.horizontalAdvance(det.text) + 12
                th = fm.height() + 5
                tx = max(4.0, min(box.left(), rect.width() - tw - 4))
                ty = box.top() - th - 4
                if ty < 36:
                    ty = box.bottom() + 4
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(3, 9, 16, 225))
                p.drawRoundedRect(QRectF(tx, ty, tw, th), 4, 4)
                p.setPen(QColor("#3EFFC0"))
                p.drawText(QRectF(tx + 6, ty, tw - 12, th), Qt.AlignVCenter, det.text)

    def _paint_footer(self, p: QPainter, rect: QRectF) -> None:
        best = max(self._detections, key=lambda d: d.conf) if self._detections else None
        if best is not None and best.text:
            p.setFont(self._font(15, True))
            p.setPen(QColor("#3EFFC0"))
            p.drawText(QPointF(14, rect.height() - 14), best.text)
            p.setFont(self._font(8.5, True))
            p.setPen(QColor(225, 240, 250))
            conf = f"置信度 {best.conf:.2f}"
            fm = QFontMetrics(p.font())
            p.drawText(
                QPointF(rect.width() - 14 - fm.horizontalAdvance(conf),
                        rect.height() - 14),
                conf,
            )
        else:
            p.setFont(self._font(9))
            p.setPen(QColor(MUTED))
            p.drawText(QPointF(14, rect.height() - 14), "等待识别…")

    def _paint_placeholder(self, p: QPainter, rect: QRectF) -> None:
        p.setBrush(QColor(10, 17, 30))
        p.setPen(QPen(QColor(BORDER), 1.4, Qt.DashLine))
        p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 11, 11)

        cx, cy = rect.center().x(), rect.center().y()
        p.setPen(Qt.NoPen)
        p.setBrush(color_alpha(ACCENT, 0.12))
        p.drawEllipse(QPointF(cx, cy - 18), 24, 24)
        p.setPen(QPen(QColor(ACCENT), 1.8))
        p.drawLine(QPointF(cx - 8, cy - 18), QPointF(cx + 8, cy - 18))
        p.drawLine(QPointF(cx, cy - 26), QPointF(cx, cy - 10))

        p.setFont(self._font(12, True))
        p.setPen(QColor(TEXT))
        p.drawText(QRectF(0, cy + 14, rect.width(), 24), Qt.AlignHCenter, "未启用通道")
        p.setFont(self._font(9))
        p.setPen(QColor(MUTED))
        p.drawText(QRectF(0, cy + 38, rect.width(), 20), Qt.AlignHCenter, "点击添加摄像头")

    def _paint_offline(self, p: QPainter, rect: QRectF) -> None:
        p.fillRect(rect, QColor(BG2))
        cx, cy = rect.center().x(), rect.center().y()
        p.setPen(QPen(QColor(FAINT), 1.7))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(cx - 24, cy - 18, 48, 32), 5, 5)
        p.drawEllipse(QPointF(cx, cy - 2), 9, 9)
        p.drawLine(QPointF(cx - 14, cy - 18), QPointF(cx - 10, cy - 26))
        p.drawLine(QPointF(cx - 10, cy - 26), QPointF(cx + 10, cy - 26))
        p.drawLine(QPointF(cx + 10, cy - 26), QPointF(cx + 14, cy - 18))

        p.setFont(self._font(10, True))
        p.setPen(QColor(TEXT))
        p.drawText(QRectF(0, cy + 20, rect.width(), 20), Qt.AlignHCenter,
                   self.cam_name or "摄像头")
        p.setFont(self._font(8.5))
        p.setPen(QColor(AMBER if "重连" in self.status or "中断" in self.status else MUTED))
        p.drawText(QRectF(0, cy + 40, rect.width(), 18), Qt.AlignHCenter, self.status)
        p.setFont(self._font(8.5, True))
        p.setPen(QColor(ACCENT))
        p.drawText(QRectF(0, cy + 62, rect.width(), 18), Qt.AlignHCenter, "点击重连")

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(RED if not self.online else GREEN))
        p.drawEllipse(QPointF(17, 19), 3.5, 3.5)
        p.setFont(self._font(9, True))
        p.setPen(QColor(TEXT))
        p.drawText(QPointF(28, 23), self.cam_name or "摄像头")

    def mousePressEvent(self, event) -> None:
        if not self.configured:
            self.add_requested.emit()
        elif not self.online and self.cam_id:
            self.reconnect_requested.emit(self.cam_id)
        super().mousePressEvent(event)


class DropArea(QFrame):
    file_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(360)
        self._hover = False
        self._batch = False

    def set_batch_mode(self, batch: bool) -> None:
        self._batch = batch
        self.update()

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._hover = True
            self.update()

    def dragLeaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def dropEvent(self, event) -> None:
        self._hover = False
        self.update()
        urls = event.mimeData().urls()
        if urls:
            self.file_selected.emit(urls[0].toLocalFile())

    def mousePressEvent(self, event) -> None:
        self.file_selected.emit("")

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        p.fillRect(rect, QColor(CARD))
        pen = QPen(QColor(ACCENT if self._hover else BORDER), 1.4, Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect.adjusted(18, 18, -18, -18), 12, 12)

        cx, cy = rect.center().x(), rect.center().y()
        p.setPen(Qt.NoPen)
        p.setBrush(color_alpha(ACCENT, 0.10))
        p.drawRoundedRect(QRectF(cx - 34, cy - 96, 68, 50), 9, 9)
        p.setPen(QPen(QColor(ACCENT), 1.8))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(cx - 24, cy - 86, 48, 32), 5, 5)
        p.setBrush(QColor(ACCENT))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx - 10, cy - 76), 3, 3)
        p.drawPolygon([
            QPointF(cx - 20, cy - 60), QPointF(cx - 6, cy - 74),
            QPointF(cx + 4, cy - 64), QPointF(cx + 14, cy - 72),
            QPointF(cx + 22, cy - 60),
        ])

        p.setFont(ui_font(17, True))
        p.setPen(QColor(TEXT))
        title = "拖拽图片文件夹到此区域" if self._batch else "拖拽图片到此区域"
        p.drawText(QRectF(0, cy - 32, rect.width(), 30), Qt.AlignHCenter, title)
        p.setFont(ui_font(10))
        p.setPen(QColor(MUTED))
        sub = "批量识别目录下的所有图片" if self._batch else "或点击选择文件"
        p.drawText(QRectF(0, cy + 2, rect.width(), 22), Qt.AlignHCenter, sub)
        p.setFont(ui_font(9))
        p.setPen(QColor(FAINT))
        p.drawText(QRectF(0, cy + 26, rect.width(), 20), Qt.AlignHCenter,
                   "支持 JPG / PNG / BMP / WEBP")

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(ACCENT))
        p.drawRoundedRect(QRectF(cx - 66, cy + 60, 132, 36), 9, 9)
        p.setPen(QColor("#04120F"))
        p.setFont(ui_font(10, True))
        button_text = "选择文件夹" if self._batch else "选择图片"
        p.drawText(QRectF(cx - 66, cy + 60, 132, 36), Qt.AlignCenter, button_text)
        p.end()


class ImageView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image: Optional[QImage] = None
        self._detections: list = []
        self.setMinimumHeight(200)

    def set_image(self, image: Optional[QImage]) -> None:
        self._image = image
        self.update()

    def set_detections(self, detections: list) -> None:
        self._detections = detections or []
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect.adjusted(1, 1, -1, -1), 9, 9)
        p.setClipPath(path)
        p.fillPath(path, QColor(BG2))
        if self._image is None or self._image.isNull():
            p.setPen(QColor(FAINT))
            p.setFont(ui_font(10))
            p.drawText(rect, Qt.AlignCenter, "识别结果预览")
            p.end()
            return

        iw, ih = self._image.width(), self._image.height()
        scale = max(rect.width() / iw, rect.height() / ih)
        dw, dh = iw * scale, ih * scale
        target = QRectF(rect.center().x() - dw / 2, rect.center().y() - dh / 2, dw, dh)
        p.drawImage(target, self._image, QRectF(0, 0, iw, ih))
        for det in self._detections:
            x1, y1, x2, y2 = det.box
            box = QRectF(target.x() + x1 * scale, target.y() + y1 * scale,
                         (x2 - x1) * scale, (y2 - y1) * scale)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(ACCENT), 2))
            p.drawRoundedRect(box, 3, 3)
            if det.text:
                p.setFont(ui_font(10, True))
                fm = QFontMetrics(p.font())
                tw = fm.horizontalAdvance(det.text) + 12
                th = fm.height() + 4
                tx = max(4.0, min(box.left(), rect.width() - tw - 4))
                ty = box.top() - th - 3
                if ty < 4:
                    ty = box.bottom() + 3
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(3, 9, 16, 225))
                p.drawRoundedRect(QRectF(tx, ty, tw, th), 4, 4)
                p.setPen(QColor("#3EFFC0"))
                p.drawText(QRectF(tx + 6, ty, tw - 12, th), Qt.AlignVCenter, det.text)
        p.end()


class LogoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 40)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(ACCENT))
        p.drawRoundedRect(QRectF(0, 0, 40, 40), 11, 11)
        p.setPen(QColor("#04211B"))
        p.setFont(ui_font(21, True))
        p.drawText(QRectF(0, 0, 40, 40), Qt.AlignCenter, "车")
        p.end()
