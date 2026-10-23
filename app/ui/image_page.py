# -*- coding: utf-8 -*-
"""图片识别页：单张 / 批量，用于验证不同场景下的识别效果。"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config import DATA_DIR
from ..core.plate import is_plausible, read_image
from ..theme import ACCENT, ACCENT2, BORDER, CARD, FAINT, GREEN, MUTED, RED, TEXT
from .widgets import (
    DropArea,
    ImageView,
    SegmentedControl,
    Thumb,
    bgr_to_qimage,
    ui_font,
)
from .workers import FunctionThread

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class RecentPlateItem(QFrame):
    def __init__(self, plate: str, conf: float, thumb: Optional[QImage], parent=None):
        super().__init__(parent)
        self.setObjectName("SubCard")
        self.setFixedHeight(52)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 10, 8)
        layout.setSpacing(10)
        layout.addWidget(Thumb(thumb, 64, 30))
        plate_label = QLabel(plate)
        plate_label.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 700;")
        layout.addWidget(plate_label, 1)
        conf_label = QLabel(f"{conf * 100:.1f}%")
        conf_label.setStyleSheet(f"color: {GREEN}; font-size: 10px; font-weight: 600;")
        layout.addWidget(conf_label)


class ResultCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._image_bgr = None
        self._image_q = None
        self._detections = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        self.view = ImageView()
        self.view.setFixedHeight(220)
        layout.addWidget(self.view)

        plate_row = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(1)
        self.plate_label = QLabel("等待识别")
        self.plate_label.setStyleSheet(
            f"color: {TEXT}; font-size: 22px; font-weight: 700;"
        )
        titles.addWidget(self.plate_label)
        self.kind_label = QLabel("选择图片后自动识别")
        self.kind_label.setObjectName("Faint")
        titles.addWidget(self.kind_label)
        plate_row.addLayout(titles, 1)
        self.conf_label = QLabel("—")
        self.conf_label.setStyleSheet(
            f"color: {GREEN}; font-size: 11px; font-weight: 700; "
            f"background: rgba(52,211,153,0.10); border-radius: 10px; padding: 4px 10px;"
        )
        plate_row.addWidget(self.conf_label, 0, Qt.AlignTop)
        layout.addLayout(plate_row)

        line = QFrame()
        line.setObjectName("HLine")
        layout.addWidget(line)

        self.fields: dict[str, QLabel] = {}
        for key in ("置信度", "检测框", "识别耗时", "图片来源"):
            row = QHBoxLayout()
            left = QLabel(key)
            left.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
            right = QLabel("—")
            right.setStyleSheet(f"color: {TEXT}; font-size: 11px; font-weight: 600;")
            right.setAlignment(Qt.AlignRight)
            row.addWidget(left)
            row.addStretch(1)
            row.addWidget(right)
            layout.addLayout(row)
            self.fields[key] = right

        buttons = QHBoxLayout()
        copy_btn = QPushButton("复制车牌号")
        copy_btn.setObjectName("Ghost")
        copy_btn.clicked.connect(self._copy)
        save_btn = QPushButton("保存结果")
        save_btn.setObjectName("Primary")
        save_btn.clicked.connect(self._save)
        buttons.addWidget(copy_btn)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)
        layout.addStretch(1)

    def set_result(self, path: Path, image_bgr, detections: list, latency: float) -> None:
        self._image_bgr = image_bgr
        self._image_q = bgr_to_qimage(image_bgr)
        self._detections = detections
        self.view.set_image(self._image_q)
        self.view.set_detections(detections)
        if detections:
            best = max(detections, key=lambda d: d.conf)
            self.plate_label.setText(best.text or "未识别")
            self.kind_label.setText(
                "车牌格式校验通过" if is_plausible(best.text) else "车牌格式存疑"
            )
            self.conf_label.setText(f"{best.conf * 100:.1f}%")
            self.fields["置信度"].setText(f"{best.conf * 100:.1f}%")
            self.fields["检测框"].setText(f"{best.width} × {best.height} px")
        else:
            self.plate_label.setText("未检测到车牌")
            self.kind_label.setText("可以尝试提高清晰度或更换角度")
            self.conf_label.setText("—")
            self.fields["置信度"].setText("—")
            self.fields["检测框"].setText("—")
        self.fields["识别耗时"].setText(f"{latency:.1f} ms")
        self.fields["图片来源"].setText(path.name)

    def clear(self) -> None:
        self._image_bgr = None
        self._image_q = None
        self._detections = []
        self.view.set_image(None)
        self.view.set_detections([])
        self.plate_label.setText("等待识别")
        self.kind_label.setText("选择图片后自动识别")
        self.conf_label.setText("—")
        for label in self.fields.values():
            label.setText("—")

    def _copy(self) -> None:
        text = self.plate_label.text()
        if text and text != "等待识别":
            QApplication.clipboard().setText(text)

    def _save(self) -> None:
        if self._image_bgr is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存识别结果", str(DATA_DIR / "result.jpg"),
            "JPEG 图片 (*.jpg);;PNG 图片 (*.png)"
        )
        if not path:
            return
        image = self._image_q.copy()
        p = QPainter(image)
        p.setRenderHint(QPainter.Antialiasing)
        for det in self._detections:
            x1, y1, x2, y2 = det.box
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(ACCENT), 2))
            p.drawRoundedRect(x1, y1, x2 - x1, y2 - y1, 3, 3)
            if det.text:
                p.setFont(ui_font(12, True))
                tw = p.fontMetrics().horizontalAdvance(det.text) + 12
                th = p.fontMetrics().height() + 4
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(3, 9, 16, 225))
                p.drawRoundedRect(x1, max(0, y1 - th - 3), tw, th, 4, 4)
                p.setPen(QColor("#3EFFC0"))
                p.drawText(x1 + 6, max(12, y1 - 6), det.text)
        p.end()
        image.save(path)


class ImagePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = None
        self._busy = False
        self._batch_paths: list[Path] = []
        self._batch_index = 0
        self._pending_path: Optional[Path] = None
        self._thread: Optional[FunctionThread] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("图片识别")
        title.setObjectName("PageTitle")
        titles.addWidget(title)
        self.subtitle = QLabel("验证不同车型、角度、光照下的识别效果")
        self.subtitle.setObjectName("Muted")
        titles.addWidget(self.subtitle)
        header.addLayout(titles)
        header.addStretch(1)
        self.mode = SegmentedControl(["单张识别", "批量识别"], 0)
        self.mode.changed.connect(self._mode_changed)
        header.addWidget(self.mode)
        root.addLayout(header)

        top = QHBoxLayout()
        top.setSpacing(14)
        self.drop = DropArea()
        self.drop.file_selected.connect(self._on_path)
        top.addWidget(self.drop, 3)
        self.result = ResultCard()
        top.addWidget(self.result, 2)
        root.addLayout(top, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(14)
        table_card = QFrame()
        table_card.setObjectName("Card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 12, 14, 12)
        table_layout.setSpacing(6)
        table_head = QHBoxLayout()
        table_title = QLabel("识别结果")
        table_title.setObjectName("SectionTitle")
        table_head.addWidget(table_title)
        table_head.addStretch(1)
        self.batch_info = QLabel("最近 5 条")
        self.batch_info.setObjectName("Faint")
        table_head.addWidget(self.batch_info)
        table_layout.addLayout(table_head)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["文件名", "车牌号", "置信度", "状态"])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setStyleSheet(
            "QHeaderView { background-color: #141F32; border: none; }"
            "QHeaderView::section { background-color: #141F32; color: #5E718C; "
            "border: none; border-bottom: 1px solid #24344C; padding: 8px 6px; }"
        )
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 4):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        table_layout.addWidget(self.table)
        bottom.addWidget(table_card, 3)

        recent_card = QFrame()
        recent_card.setObjectName("Card")
        recent_layout = QVBoxLayout(recent_card)
        recent_layout.setContentsMargins(14, 12, 14, 12)
        recent_layout.setSpacing(6)
        head = QHBoxLayout()
        recent_title = QLabel("最近识别")
        recent_title.setObjectName("SectionTitle")
        head.addWidget(recent_title)
        head.addStretch(1)
        head.addWidget(QLabel(""))
        recent_layout.addLayout(head)
        self.recent_layout = QVBoxLayout()
        self.recent_layout.setSpacing(6)
        recent_layout.addLayout(self.recent_layout)
        recent_layout.addStretch(1)
        bottom.addWidget(recent_card, 2)
        root.addLayout(bottom, 0)

        self.status = QLabel("")
        self.status.setObjectName("Faint")
        root.addWidget(self.status)

        self.table.setMinimumHeight(180)
        self.table.setMaximumHeight(210)

    def set_engine(self, engine) -> None:
        self.engine = engine

    def _mode_changed(self, index: int) -> None:
        batch = index == 1
        self.drop.set_batch_mode(batch)
        self.subtitle.setText(
            "批量识别目录下的所有图片" if batch else "验证不同车型、角度、光照下的识别效果"
        )
        self.batch_info.setText("批量任务" if batch else "最近 5 条")
        if batch:
            self.table.setRowCount(0)

    def _on_path(self, path: str) -> None:
        if self._busy:
            return
        if not path:
            if self.mode.current() == 1:
                path = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
            else:
                path, _ = QFileDialog.getOpenFileName(
                    self, "选择图片", "",
                    "图片 (*.jpg *.jpeg *.png *.bmp *.webp);;所有文件 (*.*)"
                )
        if not path:
            return
        target = Path(path)
        if target.is_dir():
            self._start_batch(target)
        elif target.suffix.lower() in IMAGE_EXTS:
            self._start_single(target)

    def _start_single(self, path: Path) -> None:
        self._batch_paths = []
        self._batch_index = 0
        self.table.setRowCount(0)
        self._process(path, batch=False)

    def _start_batch(self, directory: Path) -> None:
        paths = sorted(
            p for p in directory.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS
        )
        if not paths:
            self.status.setText("目录里没有支持的图片")
            return
        self._batch_paths = paths
        self._batch_index = 0
        self.table.setRowCount(0)
        self.batch_info.setText(f"批量 0 / {len(paths)}")
        self._process_next_batch()

    def _process_next_batch(self) -> None:
        if self._batch_index >= len(self._batch_paths):
            self._busy = False
            self.status.setText(f"批量识别完成，共 {len(self._batch_paths)} 张")
            self.batch_info.setText(f"共 {len(self._batch_paths)} 张")
            return
        path = self._batch_paths[self._batch_index]
        self.batch_info.setText(f"批量 {self._batch_index + 1} / {len(self._batch_paths)}")
        self._process(path, batch=True)

    def _process(self, path: Path, batch: bool) -> None:
        if self.engine is None:
            self.status.setText("模型还在加载，请稍候…")
            return
        image = read_image(path)
        if image is None:
            self.status.setText(f"读不到图片：{path.name}")
            if batch:
                self._add_row(path.name, "—", "—", "读取失败")
                self._batch_index += 1
                self._process_next_batch()
            return

        self._busy = True
        self._pending_path = path
        self.status.setText(f"正在识别：{path.name}")
        self.drop.setEnabled(False)

        def job():
            started = time.perf_counter()
            dets = self.engine.detect(image)
            return dets, (time.perf_counter() - started) * 1000

        thread = FunctionThread(job)
        thread.result.connect(lambda payload: self._on_result(payload, batch))
        thread.error.connect(lambda msg: self._on_error(msg, batch))
        thread.finished.connect(lambda t=thread: self._thread_finished(t))
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        thread.start()

    def _thread_finished(self, thread) -> None:
        if self._thread is thread:
            self._thread = None

    def _on_result(self, payload, batch: bool) -> None:
        detections, latency = payload
        path = self._pending_path
        image = read_image(path) if path is not None else None
        if image is None:
            self._on_error("读取图片失败", batch)
            return

        self.result.set_result(path, image, detections, latency)
        best = max(detections, key=lambda d: d.conf) if detections else None
        plate = best.text if best and best.text else "未识别"
        conf = f"{best.conf * 100:.1f}%" if best else "—"
        self._add_row(path.name, plate, conf, "成功" if best else "未检出")
        if best is not None:
            thumb = bgr_to_qimage(image[max(0, best.box[1]):best.box[3],
                                        max(0, best.box[0]):best.box[2]])
            self._add_recent(plate, best.conf, thumb)
        self.drop.setEnabled(True)

        if batch:
            self._batch_index += 1
            self._process_next_batch()
        else:
            self._busy = False
            self.status.setText(f"识别完成：{path.name}")

    def _on_error(self, message: str, batch: bool) -> None:
        self.drop.setEnabled(True)
        self._busy = False
        self.status.setText(f"识别失败：{message}")
        if batch and self._pending_path is not None:
            self._add_row(self._pending_path.name, "—", "—", "失败")
            self._batch_index += 1
            self._process_next_batch()

    def _add_row(self, name: str, plate: str, conf: str, status: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        plate_item = QTableWidgetItem(plate)
        plate_item.setForeground(QColor(GREEN))
        self.table.setItem(row, 1, plate_item)
        self.table.setItem(row, 2, QTableWidgetItem(conf))
        status_item = QTableWidgetItem(status)
        status_item.setForeground(QColor(GREEN if status == "成功" else RED))
        self.table.setItem(row, 3, status_item)
        if self.table.rowCount() > 5 and self.mode.current() == 0:
            self.table.removeRow(0)
        self.table.scrollToBottom()

    def _add_recent(self, plate: str, conf: float, thumb: Optional[QImage]) -> None:
        item = RecentPlateItem(plate, conf, thumb)
        self.recent_layout.insertWidget(0, item)
        while self.recent_layout.count() > 5:
            last = self.recent_layout.itemAt(self.recent_layout.count() - 1)
            if last is None or last.widget() is None:
                break
            widget = last.widget()
            self.recent_layout.removeWidget(widget)
            widget.deleteLater()
