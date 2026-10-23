# -*- coding: utf-8 -*-
"""用 QPainter 绘制轻量线性图标，避免外部图片资源。"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)

from ..theme import ACCENT


def _painter(size: int) -> tuple[QPixmap, QPainter]:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.scale(size / 24.0, size / 24.0)
    return pm, p


def make_pixmap(name: str, color: str = "#8FA3BF", size: int = 20) -> QPixmap:
    pm, p = _painter(size)
    c = QColor(color)
    pen = QPen(c, 1.8)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    if name == "monitor":
        p.drawRoundedRect(QRectF(3, 5, 18, 12), 2, 2)
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(10, 8.5), QPointF(10, 13.5), QPointF(14.5, 11)]))
        p.setPen(pen)
        p.drawLine(QPointF(8, 20), QPointF(16, 20))
        p.drawLine(QPointF(12, 17), QPointF(12, 20))
    elif name == "image":
        p.drawRoundedRect(QRectF(3, 4, 18, 15), 2, 2)
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(8, 9), 1.7, 1.7)
        p.setPen(pen)
        p.drawPolyline(QPolygonF([
            QPointF(4.5, 17), QPointF(9, 12), QPointF(12, 15),
            QPointF(15, 11.5), QPointF(19.5, 17),
        ]))
    elif name == "records":
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        for i in range(3):
            y = 7 + i * 5
            p.drawEllipse(QPointF(5, y), 1.1, 1.1)
        p.setPen(pen)
        for i in range(3):
            y = 7 + i * 5
            p.drawLine(QPointF(9, y), QPointF(20, y))
    elif name == "gear":
        p.drawEllipse(QPointF(12, 12), 6.4, 6.4)
        p.drawEllipse(QPointF(12, 12), 2.4, 2.4)
        for dx, dy in ((0, -9), (0, 9), (-9, 0), (9, 0),
                       (-6.4, -6.4), (6.4, -6.4), (-6.4, 6.4), (6.4, 6.4)):
            p.drawLine(QPointF(12 + dx * 0.78, 12 + dy * 0.78), QPointF(12 + dx, 12 + dy))
    elif name == "plus":
        p.drawLine(QPointF(12, 5), QPointF(12, 19))
        p.drawLine(QPointF(5, 12), QPointF(19, 12))
    elif name == "close":
        p.drawLine(QPointF(6, 6), QPointF(18, 18))
        p.drawLine(QPointF(18, 6), QPointF(6, 18))
    elif name == "refresh":
        p.drawArc(QRectF(4.5, 4.5, 15, 15), 35 * 16, 285 * 16)
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([
            QPointF(18.6, 4.2), QPointF(19.7, 9.6), QPointF(14.6, 8.0),
        ]))
    elif name == "trash":
        p.drawLine(QPointF(4, 7), QPointF(20, 7))
        p.drawLine(QPointF(9, 7), QPointF(9.5, 4.5))
        p.drawLine(QPointF(9.5, 4.5), QPointF(14.5, 4.5))
        p.drawLine(QPointF(14.5, 4.5), QPointF(15, 7))
        p.drawRoundedRect(QRectF(6, 7, 12, 13), 2, 2)
        p.drawLine(QPointF(10, 11), QPointF(10, 17))
        p.drawLine(QPointF(14, 11), QPointF(14, 17))
    elif name == "edit":
        p.drawLine(QPointF(5, 19), QPointF(16.5, 7.5))
        p.drawLine(QPointF(7.5, 20.5), QPointF(19, 9))
        p.drawLine(QPointF(5, 19), QPointF(4.5, 21))
    elif name == "check":
        p.drawPolyline(QPolygonF([QPointF(5, 12), QPointF(10, 17), QPointF(19, 7)]))
    elif name == "camera":
        p.drawRoundedRect(QRectF(3, 7, 18, 12), 2, 2)
        p.drawEllipse(QPointF(12, 13), 3.6, 3.6)
        p.drawLine(QPointF(8, 7), QPointF(9, 4.5))
        p.drawLine(QPointF(9, 4.5), QPointF(15, 4.5))
        p.drawLine(QPointF(15, 4.5), QPointF(16, 7))
    elif name == "folder":
        path = QPainterPath()
        path.moveTo(3, 7)
        path.lineTo(9, 7)
        path.lineTo(11, 9.5)
        path.lineTo(21, 9.5)
        path.lineTo(21, 19)
        path.lineTo(3, 19)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "network":
        p.drawEllipse(QPointF(12, 12), 7.5, 7.5)
        p.drawLine(QPointF(4.5, 12), QPointF(19.5, 12))
        p.drawEllipse(QPointF(12, 12), 3.2, 7.5)
    elif name == "usb":
        p.drawRoundedRect(QRectF(8, 9, 8, 11), 2, 2)
        p.drawLine(QPointF(10, 9), QPointF(10, 5))
        p.drawLine(QPointF(14, 9), QPointF(14, 5))
        p.drawLine(QPointF(8, 5), QPointF(10, 5))
        p.drawLine(QPointF(14, 5), QPointF(16, 5))
    elif name == "chevron":
        p.drawPolyline(QPolygonF([QPointF(8, 10), QPointF(12, 14), QPointF(16, 10)]))
    elif name == "warning":
        p.drawPolyline(QPolygonF([QPointF(12, 4), QPointF(21, 20), QPointF(3, 20), QPointF(12, 4)]))
        p.drawLine(QPointF(12, 9), QPointF(12, 14))
        p.setBrush(c)
        p.drawEllipse(QPointF(12, 17), 0.9, 0.9)
    else:
        p.drawEllipse(QRectF(5, 5, 14, 14))

    p.end()
    return pm


def make_icon(name: str, color: str = "#8FA3BF", size: int = 20) -> QIcon:
    return QIcon(make_pixmap(name, color, size))


def app_icon(size: int = 256) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(ACCENT))
    p.drawRoundedRect(QRectF(8, 8, size - 16, size - 16), size * 0.22, size * 0.22)
    p.setPen(QColor("#04211B"))
    font = QFont("Microsoft YaHei UI", int(size * 0.46))
    font.setBold(True)
    p.setFont(font)
    p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, "车")
    p.end()
    return QIcon(pm)
