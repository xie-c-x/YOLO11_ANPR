# -*- coding: utf-8 -*-
"""系统设置页。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import CAPTURE_DIR, CONFIG_DIR, LOG_DIR, VERSION, default_weights
from ..theme import ACCENT2, BORDER, FAINT, GREEN, MUTED, TEXT
from .widgets import ToggleSwitch


class SettingsRow(QWidget):
    def __init__(self, title: str, desc: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        texts = QVBoxLayout()
        texts.setSpacing(1)
        name = QLabel(title)
        name.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 600;")
        texts.addWidget(name)
        d = QLabel(desc)
        d.setObjectName("Faint")
        texts.addWidget(d)
        layout.addLayout(texts, 1)


class SettingsPage(QWidget):
    settings_changed = Signal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._model_name = "best.pt"
        self._device = "—"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        title = QLabel("系统设置")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        sub = QLabel("本地运行 · 配置保存在 config/cameras.json")
        sub.setObjectName("Muted")
        root.addWidget(sub)

        run_card = QFrame()
        run_card.setObjectName("Card")
        run_layout = QVBoxLayout(run_card)
        run_layout.setContentsMargins(18, 16, 18, 16)
        run_layout.setSpacing(14)
        run_title = QLabel("运行设置")
        run_title.setObjectName("SectionTitle")
        run_layout.addWidget(run_title)

        for key, title_text, desc in (
            ("auto_reconnect", "断线自动重连", "RTSP / USB 掉线后自动恢复"),
            ("save_snapshots", "识别截图本地保存", "按车牌号归档到 captures/"),
            ("autostart_monitor", "启动时自动开启监控", "程序启动后立即识别"),
        ):
            row = SettingsRow(title_text, desc)
            toggle = ToggleSwitch()
            toggle.setChecked(bool(getattr(config, key)))
            toggle.toggled.connect(lambda checked, k=key: self._set_toggle(k, checked))
            row.layout().addWidget(toggle)
            run_layout.addWidget(row)

        threshold_row = SettingsRow("检测置信度阈值", "默认 0.5；漏检可调低，误检可调高")
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.1, 0.95)
        self.threshold.setSingleStep(0.05)
        self.threshold.setDecimals(2)
        self.threshold.setValue(config.conf)
        self.threshold.setFixedWidth(90)
        self.threshold.setStyleSheet(
            "QDoubleSpinBox { background-color: #0E1727; color: #E8F0FA; "
            "border: 1px solid #24344C; border-radius: 8px; padding: 4px 8px; }"
            "QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 0px; }"
        )
        self.threshold.valueChanged.connect(self._set_threshold)
        threshold_row.layout().addWidget(self.threshold)
        run_layout.addWidget(threshold_row)

        size_row = SettingsRow("推理尺寸", "640 更快；960 对小目标更敏感")
        self.imgsz = QComboBox()
        self.imgsz.addItems(["640", "960"])
        self.imgsz.setCurrentText(str(config.imgsz))
        self.imgsz.setFixedWidth(90)
        self.imgsz.currentTextChanged.connect(self._set_imgsz)
        size_row.layout().addWidget(self.imgsz)
        run_layout.addWidget(size_row)
        root.addWidget(run_card)

        env_card = QFrame()
        env_card.setObjectName("Card")
        env_layout = QVBoxLayout(env_card)
        env_layout.setContentsMargins(18, 16, 18, 16)
        env_layout.setSpacing(10)
        env_title = QLabel("运行环境")
        env_title.setObjectName("SectionTitle")
        env_layout.addWidget(env_title)
        self.env_labels: dict[str, QLabel] = {}
        for key in ("检测模型", "计算设备", "配置文件", "日志目录", "截图目录"):
            row = QHBoxLayout()
            left = QLabel(key)
            left.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
            right = QLabel("—")
            right.setStyleSheet(f"color: {TEXT}; font-size: 11px; font-weight: 600;")
            right.setAlignment(Qt.AlignRight)
            row.addWidget(left)
            row.addStretch(1)
            row.addWidget(right)
            env_layout.addLayout(row)
            self.env_labels[key] = right

        buttons = QHBoxLayout()
        for label, path in (
            ("打开配置目录", CONFIG_DIR),
            ("打开日志目录", LOG_DIR),
            ("打开截图目录", CAPTURE_DIR),
        ):
            btn = QPushButton(label)
            btn.setObjectName("Ghost")
            btn.clicked.connect(lambda _=False, p=path: QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(p))
            ))
            buttons.addWidget(btn)
        buttons.addStretch(1)
        env_layout.addLayout(buttons)
        root.addWidget(env_card)

        root.addStretch(1)
        footer = QLabel(f"ANPR v{VERSION} · YOLO11 + RapidOCR · 本地模式")
        footer.setObjectName("Faint")
        root.addWidget(footer)

    def set_engine_info(self, model_name: str, device: str) -> None:
        self._model_name = model_name
        self._device = device
        self._refresh_env()

    def _refresh_env(self) -> None:
        self.env_labels["检测模型"].setText(self._model_name)
        self.env_labels["计算设备"].setText(self._device)
        self.env_labels["配置文件"].setText(str(CONFIG_DIR / "cameras.json"))
        self.env_labels["日志目录"].setText(str(LOG_DIR))
        self.env_labels["截图目录"].setText(str(CAPTURE_DIR))

    def _set_toggle(self, key: str, checked: bool) -> None:
        setattr(self.config, key, bool(checked))
        self.config.save()
        self.settings_changed.emit()

    def _set_threshold(self, value: float) -> None:
        self.config.conf = float(value)
        self.config.save()
        self.settings_changed.emit()

    def _set_imgsz(self, text: str) -> None:
        try:
            self.config.imgsz = int(text)
        except ValueError:
            return
        self.config.save()
        self.settings_changed.emit()
