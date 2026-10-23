# -*- coding: utf-8 -*-
"""主窗口：侧栏、顶栏、页面栈、状态栏与业务接线。"""

from __future__ import annotations

import ctypes
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QDateTime, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import AppConfig, VERSION, default_weights
from ..core.camera import CameraManager
from ..core.engine import ANPREngine
from ..core.recorder import PlateEvent, Recorder
from ..theme import ACCENT, AMBER, BORDER, FAINT, GREEN, MUTED, RED, TEXT
from .add_camera_dialog import AddCameraDialog
from .camera_drawer import CameraDrawer
from .dashboard import DashboardPage
from .icons import app_icon, make_pixmap
from .image_page import ImagePage
from .records_page import RecordsPage
from .settings_page import SettingsPage
from .widgets import LogoWidget, NavButton, ui_font
from .workers import FunctionThread


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ANPR 智能车牌识别")
        self.setWindowIcon(app_icon())
        self.resize(1440, 900)
        self.setMinimumSize(1220, 760)

        self.config = AppConfig.load()
        self.recorder = Recorder(self.config.save_snapshots)
        self.engine: ANPREngine | None = None
        self.manager: CameraManager | None = None
        self.drawer: CameraDrawer | None = None
        self._engine_thread: FunctionThread | None = None
        self._last_latency = 0.0
        self._weights_name = default_weights().name

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self._build_topbar())

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 16, 20, 12)
        content_layout.setSpacing(0)
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)
        right_layout.addWidget(content, 1)
        right_layout.addWidget(self._build_statusbar())
        root_layout.addWidget(right, 1)

        self.dashboard = DashboardPage(self.config)
        self.image_page = ImagePage()
        self.records_page = RecordsPage(self.recorder)
        self.settings_page = SettingsPage(self.config)
        for page in (self.dashboard, self.image_page, self.records_page, self.settings_page):
            self.stack.addWidget(page)

        self.dashboard.set_today_base(len(self.recorder.load_today()))
        self.dashboard.set_loading("正在加载识别模型…（首次约 10–20 秒）")
        for cfg in self.config.channels[: self.config.enabled_count]:
            self.dashboard.set_status(cfg.id, False, "模型加载中…")
        self._wire()
        self._update_clock()
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._tick)
        self._clock_timer.start()

        QTimer.singleShot(120, self._apply_dark_titlebar)
        QTimer.singleShot(250, self._load_engine)

    # ---------------- 界面构建 ----------------
    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(212)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(6)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(12)
        logo_row.addWidget(LogoWidget())
        names = QVBoxLayout()
        names.setSpacing(0)
        app_name = QLabel("ANPR")
        app_name.setStyleSheet(f"color: {TEXT}; font-size: 18px; font-weight: 700;")
        names.addWidget(app_name)
        sub = QLabel("智能车牌识别系统")
        sub.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        names.addWidget(sub)
        logo_row.addLayout(names)
        logo_row.addStretch(1)
        layout.addLayout(logo_row)
        layout.addSpacing(14)

        section = QLabel("工作台")
        section.setStyleSheet(f"color: {FAINT}; font-size: 10px; font-weight: 600;")
        layout.addWidget(section)
        layout.addSpacing(2)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        navs = [
            ("monitor", "实时监控"),
            ("image", "图片识别"),
            ("records", "识别记录"),
            ("gear", "系统设置"),
        ]
        for i, (icon, text) in enumerate(navs):
            btn = NavButton(icon, text)
            self.nav_group.addButton(btn, i)
            layout.addWidget(btn)
        self.nav_group.button(0).setChecked(True)
        self.nav_group.idClicked.connect(self._switch_page)

        layout.addStretch(1)

        env = QFrame()
        env.setObjectName("SubCard")
        env_layout = QVBoxLayout(env)
        env_layout.setContentsMargins(12, 10, 12, 10)
        env_layout.setSpacing(3)
        env_title = QLabel("运行环境")
        env_title.setStyleSheet(f"color: {FAINT}; font-size: 9px; font-weight: 600;")
        env_layout.addWidget(env_title)
        self.env_model = QLabel("YOLO11n · RapidOCR")
        self.env_model.setStyleSheet(f"color: {TEXT}; font-size: 11px; font-weight: 600;")
        env_layout.addWidget(self.env_model)
        self.env_device = QLabel("模型加载中…")
        self.env_device.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        env_layout.addWidget(self.env_device)
        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {AMBER}; font-size: 10px;")
        status_row.addWidget(dot)
        self.env_status = QLabel("准备中")
        self.env_status.setStyleSheet(f"color: {AMBER}; font-size: 10px;")
        status_row.addWidget(self.env_status)
        status_row.addStretch(1)
        env_layout.addLayout(status_row)
        layout.addWidget(env)
        return sidebar

    def _build_topbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(68)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 10, 20, 10)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        title = QLabel("ANPR 智能监控中心")
        title.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700;")
        titles.addWidget(title)
        sub = QLabel("本地推理 · 数据不出设备")
        sub.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        titles.addWidget(sub)
        layout.addLayout(titles)
        layout.addStretch(1)

        self.top_status = QLabel("●  模型加载中")
        self.top_status.setStyleSheet(
            f"color: {AMBER}; font-size: 11px; font-weight: 600; "
            f"background: rgba(245,158,11,0.10); border: 1px solid rgba(245,158,11,0.25); "
            f"border-radius: 12px; padding: 4px 10px;"
        )
        layout.addWidget(self.top_status)
        layout.addSpacing(18)

        clock_box = QVBoxLayout()
        clock_box.setSpacing(0)
        self.clock_label = QLabel("--:--:--")
        self.clock_label.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700;")
        self.clock_label.setAlignment(Qt.AlignRight)
        clock_box.addWidget(self.clock_label)
        self.date_label = QLabel("----")
        self.date_label.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        self.date_label.setAlignment(Qt.AlignRight)
        clock_box.addWidget(self.date_label)
        layout.addLayout(clock_box)
        return bar

    def _build_statusbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(32)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 0, 18, 0)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {GREEN}; font-size: 10px;")
        layout.addWidget(dot)
        self.status_text = QLabel("模型加载中…")
        self.status_text.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        layout.addWidget(self.status_text)
        layout.addStretch(1)
        version = QLabel(f"v{VERSION}  ·  本地模式")
        version.setStyleSheet(f"color: {FAINT}; font-size: 10px;")
        layout.addWidget(version)
        return bar

    # ---------------- 接线 ----------------
    def _wire(self) -> None:
        self.dashboard.count_changed.connect(self._on_count_changed)
        self.dashboard.manage_requested.connect(self._open_drawer)
        self.dashboard.add_requested.connect(lambda: self._open_add_dialog(None))
        self.dashboard.reconnect_requested.connect(self._reconnect)
        self.settings_page.settings_changed.connect(self._on_settings_changed)

    def _switch_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        if index == 2:
            self.records_page.refresh()

    # ---------------- 引擎 ----------------
    def _load_engine(self) -> None:
        weights = default_weights()
        if not weights.exists():
            self._engine_failed(f"找不到模型文件：{weights}")
            return
        self._weights_name = weights.name
        thread = FunctionThread(
            lambda: ANPREngine(
                weights,
                device="auto",
                imgsz=self.config.imgsz,
                conf=self.config.conf,
            )
        )
        thread.result.connect(self._engine_ready)
        thread.error.connect(self._engine_failed)
        thread.finished.connect(thread.deleteLater)
        self._engine_thread = thread
        thread.start()

    def _engine_ready(self, engine: ANPREngine) -> None:
        self._engine_thread = None
        self.engine = engine
        self.env_device.setText(engine.device_name)
        self.env_status.setText("服务正常")
        self.env_status.setStyleSheet(f"color: {GREEN}; font-size: 10px;")
        self.settings_page.set_engine_info(self._weights_name, engine.device_name)
        self.image_page.set_engine(engine)

        self.manager = CameraManager(engine, auto_reconnect=self.config.auto_reconnect)
        self.manager.frame_ready.connect(self.dashboard.update_frame)
        self.manager.results_ready.connect(self._on_results)
        self.manager.status_changed.connect(self.dashboard.set_status)
        self.manager.fps_updated.connect(self.dashboard.set_fps)
        self.manager.plate_event.connect(self._on_plate)
        if self.drawer is not None:
            self.drawer.manager = self.manager

        self._set_top_status("●  系统运行中", GREEN, "rgba(52,211,153,0.10)", "rgba(52,211,153,0.25)")
        if self.config.autostart_monitor:
            self.manager.start(self.config.channels, self.config.enabled_count)
            self.status_text.setText("监控运行中")
        else:
            self.status_text.setText("模型已就绪，监控未启动")
        self.dashboard.set_channels(self.config.channels, self.config.enabled_count)

    def _engine_failed(self, message: str) -> None:
        self._engine_thread = None
        self._set_top_status("●  模型加载失败", RED, "rgba(248,113,113,0.10)", "rgba(248,113,113,0.25)")
        self.env_status.setText("异常")
        self.env_status.setStyleSheet(f"color: {RED}; font-size: 10px;")
        self.status_text.setText("模型加载失败")
        self.dashboard.set_loading("模型加载失败，请检查模型文件")
        QMessageBox.critical(self, "模型加载失败", message)

    def _set_top_status(self, text: str, color: str, bg: str, border: str) -> None:
        self.top_status.setText(text)
        self.top_status.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: 600; "
            f"background: {bg}; border: 1px solid {border}; "
            f"border-radius: 12px; padding: 4px 10px;"
        )

    # ---------------- 业务 ----------------
    def _on_results(self, cam_id: str, detections: list, latency: float) -> None:
        self._last_latency = self._last_latency * 0.7 + latency * 0.3
        self.dashboard.update_results(cam_id, detections, latency)

    def _on_plate(self, event: PlateEvent) -> None:
        self.recorder.log(event)
        self.dashboard.add_plate(event)

    def _on_count_changed(self, count: int) -> None:
        self.config.enabled_count = max(1, min(4, count))
        self.config.save()
        self.dashboard.set_channels(self.config.channels, self.config.enabled_count)
        if self.manager is not None:
            self.manager.start(self.config.channels, self.config.enabled_count)

    def _on_settings_changed(self) -> None:
        if self.engine is not None:
            self.engine.conf = self.config.conf
            self.engine.imgsz = self.config.imgsz
        self.recorder.save_snapshots = self.config.save_snapshots
        if self.manager is not None:
            self.manager.auto_reconnect = self.config.auto_reconnect

    def _reconnect(self, cam_id: str) -> None:
        if self.manager is not None:
            self.manager.reconnect(cam_id)

    # ---------------- 摄像头管理 ----------------
    def _open_drawer(self) -> None:
        if self.drawer is None:
            self.drawer = CameraDrawer(self.config, self.manager, self.centralWidget())
            self.drawer.add_requested.connect(lambda: self._open_add_dialog(None))
            self.drawer.edit_requested.connect(lambda cfg: self._open_add_dialog(cfg))
            self.drawer.remove_requested.connect(self._remove_camera)
            self.drawer.settings_changed.connect(self._on_settings_changed)
        self.drawer.manager = self.manager
        self.drawer.setGeometry(self.centralWidget().rect())
        self.drawer.refresh()
        self.drawer.show()
        self.drawer.raise_()
        self.drawer.setFocus()

    def _open_add_dialog(self, edit=None) -> None:
        dialog = AddCameraDialog(self, edit=edit)
        dialog.camera_saved.connect(self._camera_saved)
        dialog.exec()
        if self.drawer is not None and self.drawer.isVisible():
            self.drawer.refresh()

    def _camera_saved(self, cfg) -> None:
        existing = next((c for c in self.config.channels if c.id == cfg.id), None)
        if existing is None:
            duplicate = next(
                (c for c in self.config.channels
                 if c.kind == cfg.kind and c.source == cfg.source),
                None,
            )
            if duplicate is not None:
                QMessageBox.warning(
                    self, "重复摄像头",
                    f"该地址已经配置为“{duplicate.name}”，请勿重复添加。",
                )
                return
        if existing is not None:
            index = self.config.channels.index(existing)
            self.config.channels[index] = cfg
        elif len(self.config.channels) < 4:
            self.config.channels.append(cfg)
        self.config.enabled_count = min(
            4, max(self.config.enabled_count, len(self.config.channels))
        )
        self.config.save()
        self.dashboard.set_channels(self.config.channels, self.config.enabled_count)
        if self.manager is not None:
            self.manager.start(self.config.channels, self.config.enabled_count)
        if self.drawer is not None:
            self.drawer.refresh()

    def _remove_camera(self, cfg) -> None:
        self.config.channels = [c for c in self.config.channels if c.id != cfg.id]
        self.config.enabled_count = max(
            1, min(self.config.enabled_count, max(1, len(self.config.channels)))
        )
        self.config.save()
        self.dashboard.set_channels(self.config.channels, self.config.enabled_count)
        if self.manager is not None:
            self.manager.start(self.config.channels, self.config.enabled_count)
        if self.drawer is not None:
            self.drawer.refresh()

    # ---------------- 时钟 / 状态 ----------------
    def _update_clock(self) -> None:
        now = QDateTime.currentDateTime()
        self.clock_label.setText(now.toString("HH:mm:ss"))
        weekdays = "一二三四五六日"
        weekday = weekdays[now.date().dayOfWeek() - 1]
        self.date_label.setText(f"{now.toString('yyyy-MM-dd')}  星期{weekday}")

    def _tick(self) -> None:
        self._update_clock()
        if self.manager is not None and self.engine is not None:
            online = self.manager.online_count()
            total = len(self.manager.states)
            self.status_text.setText(
                f"模型 {self._weights_name}   ·   RapidOCR   ·   "
                f"平均 {self._last_latency:.0f}ms/帧   ·   {online}/{total} 路在线"
            )
            self.dashboard.update_system(
                self._weights_name, self.engine.device_name, self.dashboard.runtime_text()
            )

    # ---------------- 窗口 ----------------
    def _apply_dark_titlebar(self) -> None:
        if sys.platform != "win32":
            return
        try:
            hwnd = int(self.winId())
            value = ctypes.c_int(1)
            for attr in (20, 19):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
                )
        except Exception:
            pass

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.drawer is not None and self.drawer.isVisible():
            self.drawer.setGeometry(self.centralWidget().rect())

    def closeEvent(self, event) -> None:
        try:
            if self.manager is not None:
                self.manager.stop()
                self.manager = None
            if self._engine_thread is not None and self._engine_thread.isRunning():
                if not self._engine_thread.wait(5000):
                    self._engine_thread.terminate()
                    self._engine_thread.wait(1000)
                self._engine_thread = None
            self.config.save()
        finally:
            super().closeEvent(event)
