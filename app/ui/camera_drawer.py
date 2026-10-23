# -*- coding: utf-8 -*-
"""右侧摄像头管理抽屉。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..config import CameraConfig
from ..core.onvif import test_rtsp
from ..theme import ACCENT, ACCENT2, AMBER, BORDER, CARD, CARD2, FAINT, GREEN, MUTED, RED, TEXT
from .icons import make_icon
from .widgets import IconButton, ToggleSwitch, ui_font
from .workers import FunctionThread


class CameraCard(QFrame):
    edit_requested = Signal(object)
    remove_requested = Signal(object)

    def __init__(self, index: int, cfg: CameraConfig, online: bool, message: str,
                 last_plate: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("SubCard")
        self.cfg = cfg
        self.setFixedHeight(104)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        number = QLabel(f"{index + 1:02d}")
        number.setStyleSheet(f"color: {FAINT}; font-size: 11px; font-weight: 700;")
        number.setFixedWidth(22)
        number.setAlignment(Qt.AlignTop)
        layout.addWidget(number)

        middle = QVBoxLayout()
        middle.setSpacing(2)
        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name = QLabel(cfg.name)
        name.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700;")
        name_row.addWidget(name)
        badge = QLabel("USB" if cfg.kind == "usb" else "RTSP")
        badge_color = ACCENT2 if cfg.kind == "usb" else "#A78BFA"
        badge.setStyleSheet(
            f"color: {badge_color}; font-size: 9px; font-weight: 700; "
            f"background: rgba(56,189,248,0.10); border-radius: 8px; padding: 2px 7px;"
        )
        name_row.addWidget(badge)
        name_row.addStretch(1)
        middle.addLayout(name_row)

        source = cfg.source if cfg.kind == "rtsp" else f"USB 设备 {cfg.source}"
        if len(source) > 46:
            source = source[:43] + "…"
        source_label = QLabel(source)
        source_label.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        source_label.setToolTip(source)
        middle.addWidget(source_label)
        recent = QLabel(f"最近：{last_plate}" if last_plate else f"状态：{message}")
        recent.setStyleSheet(f"color: {FAINT}; font-size: 10px;")
        recent.setToolTip(message)
        middle.addWidget(recent)
        layout.addLayout(middle, 1)

        right = QVBoxLayout()
        right.setSpacing(4)
        status = QLabel("● 在线" if online else "● 离线")
        status.setStyleSheet(
            f"color: {GREEN if online else RED}; font-size: 10px; font-weight: 600;"
        )
        status.setAlignment(Qt.AlignRight)
        right.addWidget(status)

        actions = QHBoxLayout()
        actions.setSpacing(4)
        test_btn = QPushButton("测试")
        test_btn.setObjectName("Ghost")
        test_btn.setFixedHeight(22)
        test_btn.clicked.connect(self._test)
        edit_btn = QPushButton("编辑")
        edit_btn.setObjectName("Ghost")
        edit_btn.setFixedHeight(22)
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.cfg))
        remove_btn = QPushButton("移除")
        remove_btn.setObjectName("Danger")
        remove_btn.setFixedHeight(22)
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.cfg))
        actions.addWidget(test_btn)
        actions.addWidget(edit_btn)
        actions.addWidget(remove_btn)
        right.addLayout(actions)
        right.addStretch(1)
        layout.addLayout(right)

        self._thread: Optional[FunctionThread] = None

    def _test(self) -> None:
        if self.cfg.kind != "rtsp":
            QMessageBox.information(
                self, "USB 摄像头",
                f"设备号 {self.cfg.source}\n请在主界面观察该路画面是否正常。",
            )
            return
        if self._thread is not None and self._thread.isRunning():
            return
        QMessageBox.information(self, "测试连接", "正在测试 RTSP，请稍候…")
        thread = FunctionThread(lambda: test_rtsp(self.cfg.source, 8))
        thread.result.connect(self._test_done)
        thread.error.connect(lambda msg: QMessageBox.warning(self, "测试失败", msg))
        thread.finished.connect(lambda t=thread: setattr(self, "_thread", None))
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        thread.start()

    def _test_done(self, result) -> None:
        if result.ok:
            QMessageBox.information(
                self, "连接成功",
                f"{result.width}×{result.height} @ {result.fps:.0f} FPS",
            )
        else:
            QMessageBox.warning(self, "连接失败", result.message)


class CameraDrawer(QWidget):
    closed = Signal()
    add_requested = Signal()
    edit_requested = Signal(object)
    remove_requested = Signal(object)
    settings_changed = Signal()

    def __init__(self, config, manager, parent=None):
        super().__init__(parent)
        self.config = config
        self.manager = manager
        self.setObjectName("DrawerOverlay")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("QWidget#DrawerOverlay { background: rgba(3, 7, 14, 150); }")
        self.hide()

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addStretch(1)
        self.panel = QFrame()
        self.panel.setObjectName("Drawer")
        self.panel.setFixedWidth(430)
        root.addWidget(self.panel)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("摄像头管理")
        title.setObjectName("PageTitle")
        titles.addWidget(title)
        sub = QLabel("USB / RTSP 双模式 · 最多 4 路")
        sub.setObjectName("Muted")
        titles.addWidget(sub)
        head.addLayout(titles)
        head.addStretch(1)
        close = IconButton("close", "关闭")
        close.clicked.connect(self.close_drawer)
        head.addWidget(close, 0, Qt.AlignTop)
        layout.addLayout(head)

        self.chips = QHBoxLayout()
        self.chips.setSpacing(8)
        layout.addLayout(self.chips)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.holder = QWidget()
        self.cards_layout = QVBoxLayout(self.holder)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(8)
        self.cards_layout.addStretch(1)
        self.scroll.setWidget(self.holder)
        layout.addWidget(self.scroll, 1)

        self.add_btn = QPushButton("＋  添加摄像头        USB / RTSP")
        self.add_btn.setObjectName("Ghost")
        self.add_btn.setFixedHeight(44)
        self.add_btn.setStyleSheet(
            f"QPushButton {{ border: 1px dashed {BORDER}; border-radius: 10px; "
            f"color: {ACCENT}; font-weight: 600; }}"
            f"QPushButton:hover {{ background: {CARD2}; }}"
        )
        self.add_btn.clicked.connect(self.add_requested.emit)
        layout.addWidget(self.add_btn)

        toggle_box = QFrame()
        toggle_box.setObjectName("SubCard")
        toggle_layout = QVBoxLayout(toggle_box)
        toggle_layout.setContentsMargins(14, 10, 14, 10)
        toggle_layout.setSpacing(8)
        self.toggles: dict[str, ToggleSwitch] = {}
        for key, label, desc in (
            ("auto_reconnect", "断线自动重连", "摄像头掉线后自动恢复"),
            ("save_snapshots", "识别截图本地保存", "按车牌号归档到 captures/"),
            ("autostart_monitor", "启动时自动开启监控", "打开程序即开始识别"),
        ):
            row = QHBoxLayout()
            texts = QVBoxLayout()
            texts.setSpacing(1)
            name = QLabel(label)
            name.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 600;")
            texts.addWidget(name)
            d = QLabel(desc)
            d.setObjectName("Faint")
            texts.addWidget(d)
            row.addLayout(texts, 1)
            toggle = ToggleSwitch()
            toggle.setChecked(bool(getattr(self.config, key)))
            toggle.toggled.connect(
                lambda checked, k=key: self._on_toggle(k, checked)
            )
            row.addWidget(toggle)
            self.toggles[key] = toggle
            toggle_layout.addLayout(row)
        layout.addWidget(toggle_box)

        footer = QHBoxLayout()
        path = QLabel("配置保存在 config/cameras.json")
        path.setObjectName("Faint")
        footer.addWidget(path)
        footer.addStretch(1)
        save = QPushButton("保存配置")
        save.setObjectName("Primary")
        save.clicked.connect(self._save)
        footer.addWidget(save)
        layout.addLayout(footer)

    def refresh(self) -> None:
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

        channels = self.config.channels
        online = 0
        for i, cfg in enumerate(channels):
            state = None
            if self.manager is not None:
                state = self.manager.state_snapshot().get(cfg.id)
            is_online = bool(state and state.online)
            online += int(is_online)
            last = ""
            if self.manager is not None:
                last = self.manager.get_last_plate(cfg.id)[0]
            card = CameraCard(
                i, cfg, is_online,
                state.message if state else "未启动",
                last,
            )
            card.edit_requested.connect(self.edit_requested.emit)
            card.remove_requested.connect(self._confirm_remove)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

        while self.chips.count():
            item = self.chips.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for text, color in (
            (f"{len(channels)} 路通道", MUTED),
            (f"{online} 在线", GREEN),
            (f"{max(0, len(channels) - online)} 离线", RED),
        ):
            chip = QLabel(text)
            chip.setStyleSheet(
                f"color: {color}; font-size: 10px; font-weight: 600; "
                f"background: rgba(143,163,191,0.08); border: 1px solid {BORDER}; "
                f"border-radius: 10px; padding: 3px 9px;"
            )
            self.chips.addWidget(chip)
        self.chips.addStretch(1)

        self.add_btn.setEnabled(len(channels) < 4)
        if len(channels) >= 4:
            self.add_btn.setText("已达 4 路上限")
        else:
            self.add_btn.setText("＋  添加摄像头        USB / RTSP")

    def _on_toggle(self, key: str, checked: bool) -> None:
        setattr(self.config, key, bool(checked))
        self.config.save()
        self.settings_changed.emit()

    def _confirm_remove(self, cfg: CameraConfig) -> None:
        answer = QMessageBox.question(
            self, "移除摄像头",
            f"确定移除“{cfg.name}”吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.remove_requested.emit(cfg)

    def _save(self) -> None:
        self.config.save()
        self.close_drawer()

    def close_drawer(self) -> None:
        self.hide()
        self.closed.emit()

    def showEvent(self, event) -> None:
        self.refresh()
        super().showEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.position().x() < self.width() - self.panel.width():
            self.close_drawer()
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.close_drawer()
        else:
            super().keyPressEvent(event)
