# -*- coding: utf-8 -*-
"""实时监控页：摄像头网格、统计卡、右侧后台车牌记录。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..config import CameraConfig
from ..core.recorder import PlateEvent
from ..theme import ACCENT, ACCENT2, BORDER, BORDER_SOFT, CARD, CARD2, FAINT, GREEN, MUTED, TEXT
from .icons import make_pixmap
from .widgets import (
    CameraTile,
    IconButton,
    PlateLogItem,
    SegmentedControl,
    StatCard,
    bgr_to_qimage,
    ui_font,
)


class PlateLogPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RightPanel")
        self.setFixedWidth(340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(10)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        label = QLabel("实时识别记录")
        label.setObjectName("SectionTitle")
        titles.addWidget(label)
        sub = QLabel("后台运行 · 自动写入 CSV")
        sub.setObjectName("Faint")
        titles.addWidget(sub)
        head.addLayout(titles)
        head.addStretch(1)
        running = QLabel("●  运行中")
        running.setStyleSheet(
            f"color: {GREEN}; font-size: 11px; font-weight: 600; "
            f"background: rgba(52,211,153,0.10); border: 1px solid rgba(52,211,153,0.22); "
            f"border-radius: 10px; padding: 3px 8px;"
        )
        head.addWidget(running, 0, Qt.AlignTop)
        layout.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.holder = QWidget()
        self.log_layout = QVBoxLayout(self.holder)
        self.log_layout.setContentsMargins(0, 0, 0, 0)
        self.log_layout.setSpacing(8)
        self.empty = QLabel("等待识别…\n摄像头识别到车牌后会显示在这里")
        self.empty.setObjectName("Faint")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setMinimumHeight(160)
        self.log_layout.addWidget(self.empty)
        self.log_layout.addStretch(1)
        self.scroll.setWidget(self.holder)
        layout.addWidget(self.scroll, 1)

        self.status_card = QFrame()
        self.status_card.setObjectName("SubCard")
        status_layout = QVBoxLayout(self.status_card)
        status_layout.setContentsMargins(14, 12, 14, 12)
        status_layout.setSpacing(8)
        title = QLabel("系统状态")
        title.setObjectName("CardTitle")
        status_layout.addWidget(title)
        self.value_labels: dict[str, QLabel] = {}
        for key in ("检测模型", "识别引擎", "计算设备", "实时帧率", "今日识别", "运行时长"):
            row = QHBoxLayout()
            left = QLabel(key)
            left.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
            right = QLabel("—")
            right.setStyleSheet(f"color: {TEXT}; font-size: 11px; font-weight: 600;")
            right.setAlignment(Qt.AlignRight)
            row.addWidget(left)
            row.addStretch(1)
            row.addWidget(right)
            status_layout.addLayout(row)
            self.value_labels[key] = right
        layout.addWidget(self.status_card)

    def add_event(self, event: PlateEvent) -> None:
        if self.empty is not None:
            self.empty.hide()
        thumb = None
        if event.crop is not None and event.crop.size:
            thumb = bgr_to_qimage(event.crop)
        item = PlateLogItem(
            plate=event.plate,
            cam_name=event.cam_name,
            time_text=event.timestamp.strftime("%H:%M:%S"),
            conf=event.conf,
            thumb=thumb,
        )
        self.log_layout.insertWidget(0, item)
        while self.log_layout.count() > 32:
            last = self.log_layout.itemAt(self.log_layout.count() - 2)
            if last is None or last.widget() is None:
                break
            widget = last.widget()
            self.log_layout.removeWidget(widget)
            widget.deleteLater()

    def update_system(self, model_name: str, device_name: str, fps: float,
                      today_count: int, runtime: str) -> None:
        values = {
            "检测模型": model_name,
            "识别引擎": "RapidOCR",
            "计算设备": device_name,
            "实时帧率": f"{fps:.1f} FPS",
            "今日识别": f"{today_count} 次",
            "运行时长": runtime,
        }
        for key, value in values.items():
            if key in self.value_labels:
                self.value_labels[key].setText(value)


class DashboardPage(QWidget):
    count_changed = Signal(int)
    manage_requested = Signal()
    add_requested = Signal()
    reconnect_requested = Signal(str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._tiles: dict[str, CameraTile] = {}
        self._session_count = 0
        self._today_base = 0
        self._conf_sum = 0.0
        self._conf_count = 0
        self._online = 0
        self._total = 0
        self._started = datetime.now()
        self._fps = 0.0

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(14)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.title = QLabel("实时监控")
        self.title.setObjectName("PageTitle")
        titles.addWidget(self.title)
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("Muted")
        titles.addWidget(self.subtitle)
        header.addLayout(titles)
        header.addStretch(1)

        count_label = QLabel("摄像头数量")
        count_label.setObjectName("Muted")
        count_label.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        header.addWidget(count_label)
        self.count_control = SegmentedControl(["1", "2", "3", "4"], config.enabled_count - 1)
        self.count_control.changed.connect(self._on_count_changed)
        header.addWidget(self.count_control)
        self.manage_btn = IconButton("gear", "摄像头管理")
        self.manage_btn.clicked.connect(self.manage_requested)
        header.addWidget(self.manage_btn)
        left.addLayout(header)

        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(14)
        for i in range(2):
            self.grid.setRowStretch(i, 1)
            self.grid.setColumnStretch(i, 1)
        self.grid_host.setMinimumHeight(380)
        left.addWidget(self.grid_host, 1)

        stats = QHBoxLayout()
        stats.setSpacing(14)
        self.card_count = StatCard("今日识别", "0", "本次运行", "camera", ACCENT, "spark")
        self.card_conf = StatCard("平均置信度", "—", "实时统计", "check", ACCENT2, "progress")
        self.card_online = StatCard("在线摄像头", "0 / 0", "全部在线", "monitor", GREEN, "dots")
        for card in (self.card_count, self.card_conf, self.card_online):
            stats.addWidget(card, 1)
        left.addLayout(stats)

        root.addLayout(left, 1)
        self.log_panel = PlateLogPanel()
        root.addWidget(self.log_panel)

        self.set_channels(config.channels, config.enabled_count)

    # ---------------- 网格 ----------------
    def _clear_grid(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._tiles.clear()

    def set_channels(self, channels: list[CameraConfig], enabled_count: int) -> None:
        self._clear_grid()
        count = max(1, min(4, int(enabled_count)))
        self.count_control.setCurrent(count - 1, False)
        self.subtitle.setText(f"{count} 路摄像头 · 识别结果实时写入后台")
        self._total = count

        active = channels[:count]
        if count == 1:
            tile = CameraTile(0)
            self._prepare_tile(tile, active[0] if active else None)
            self.grid.addWidget(tile, 0, 0, 2, 2)
        else:
            for slot in range(4):
                tile = CameraTile(slot)
                cfg = active[slot] if slot < len(active) else None
                self._prepare_tile(tile, cfg)
                self.grid.addWidget(tile, slot // 2, slot % 2)
        self._update_online()

    def _prepare_tile(self, tile: CameraTile, cfg: Optional[CameraConfig]) -> None:
        if cfg is None:
            tile.set_placeholder()
        else:
            tile.set_camera(cfg.id, cfg.label, cfg.kind)
            self._tiles[cfg.id] = tile
        tile.add_requested.connect(self.add_requested)
        tile.reconnect_requested.connect(self.reconnect_requested)

    def _on_count_changed(self, index: int) -> None:
        count = index + 1
        self.subtitle.setText(f"{count} 路摄像头 · 识别结果实时写入后台")
        self.count_changed.emit(count)

    def set_count(self, count: int) -> None:
        self.count_control.setCurrent(max(0, min(3, count - 1)), False)

    def set_loading(self, text: str) -> None:
        self.subtitle.setText(text)

    # ---------------- 实时更新 ----------------
    def update_frame(self, cam_id: str, image) -> None:
        tile = self._tiles.get(cam_id)
        if tile is not None:
            tile.set_frame(image)

    def update_results(self, cam_id: str, detections: list, latency: float) -> None:
        tile = self._tiles.get(cam_id)
        if tile is not None:
            tile.set_detections(detections)

    def set_status(self, cam_id: str, online: bool, message: str) -> None:
        tile = self._tiles.get(cam_id)
        if tile is not None:
            tile.set_status(online, message)
        self._update_online()

    def set_fps(self, cam_id: str, fps: float) -> None:
        tile = self._tiles.get(cam_id)
        if tile is not None:
            tile.set_fps(fps)
        self._fps = max(self._fps * 0.7, fps)

    def _update_online(self) -> None:
        online = sum(1 for tile in self._tiles.values() if tile.online)
        self._online = online
        self.card_online.set_value(f"{online} / {self._total}")
        note = "全部在线" if online == self._total else f"{self._total - online} 路离线"
        color = GREEN if online == self._total else "#F59E0B"
        self.card_online.set_note(note, color)
        dots = getattr(self.card_online.extra, "set_count", None)
        if dots:
            dots(online)

    def add_plate(self, event: PlateEvent) -> None:
        self.log_panel.add_event(event)
        self._session_count += 1
        self._conf_sum += event.conf
        self._conf_count += 1
        self.card_count.set_value(f"{self._today_base + self._session_count:,}")
        avg = self._conf_sum / max(1, self._conf_count)
        self.card_conf.set_value(f"{avg * 100:.1f}%")
        self.card_conf.set_progress(avg)

    def set_today_base(self, count: int) -> None:
        self._today_base = max(0, int(count))
        self.card_count.set_value(f"{self._today_base + self._session_count:,}")

    def update_system(self, model_name: str, device_name: str, runtime: str) -> None:
        self.log_panel.update_system(
            model_name=model_name,
            device_name=device_name,
            fps=self._fps,
            today_count=self._today_base + self._session_count,
            runtime=runtime,
        )

    def runtime_text(self) -> str:
        seconds = int((datetime.now() - self._started).total_seconds())
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h}h {m:02d}m"
