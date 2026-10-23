# -*- coding: utf-8 -*-
"""添加 / 编辑摄像头弹窗：ONVIF、USB、手动 RTSP。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import CameraConfig
from ..core.onvif import (
    OnvifDevice,
    discover_onvif,
    probe_usb,
    resolve_onvif_rtsp,
    test_rtsp,
)
from ..theme import ACCENT, BORDER, FAINT, GREEN, MUTED, RED, TEXT
from .widgets import ui_font
from .workers import FunctionThread


class AddCameraDialog(QDialog):
    camera_saved = Signal(object)

    def __init__(self, parent=None, edit: Optional[CameraConfig] = None):
        super().__init__(parent)
        self.edit = edit
        self._thread: Optional[FunctionThread] = None
        self._devices: list[OnvifDevice] = []
        self.setWindowTitle("编辑摄像头" if edit else "添加摄像头")
        self.resize(720, 620)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = QLabel("编辑摄像头" if edit else "添加摄像头")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        sub = QLabel("支持 ONVIF 自动发现、USB 本机设备与手动 RTSP 地址")
        sub.setObjectName("Muted")
        root.addWidget(sub)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_onvif_tab(), "ONVIF 自动发现")
        self.tabs.addTab(self._build_usb_tab(), "USB 本机设备")
        self.tabs.addTab(self._build_rtsp_tab(), "手动 RTSP")
        root.addWidget(self.tabs, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        root.addLayout(footer)

        if edit is not None:
            self._load_edit(edit)

    # ---------------- ONVIF ----------------
    def _build_onvif_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        top = QHBoxLayout()
        net_label = QLabel("扫描网段")
        net_label.setObjectName("Muted")
        top.addWidget(net_label)
        self.net_input = QLineEdit("192.168.1.0 / 24")
        self.net_input.setReadOnly(True)
        self.net_input.setFixedWidth(170)
        top.addWidget(self.net_input)
        self.scan_btn = QPushButton("开始扫描")
        self.scan_btn.setObjectName("Primary")
        self.scan_btn.clicked.connect(self._scan_onvif)
        top.addWidget(self.scan_btn)
        top.addStretch(1)
        layout.addLayout(top)

        self.onvif_table = self._make_table(["设备", "IP 地址", "状态", "操作"])
        layout.addWidget(self.onvif_table, 1)

        self.onvif_status = QLabel("点击“开始扫描”查找同一网段的 ONVIF 摄像头")
        self.onvif_status.setObjectName("Faint")
        layout.addWidget(self.onvif_status)

        creds = QHBoxLayout()
        creds.setSpacing(8)
        creds.addWidget(QLabel("用户名"))
        self.onvif_user = QLineEdit("admin")
        self.onvif_user.setPlaceholderText("用户名")
        creds.addWidget(self.onvif_user, 1)
        creds.addWidget(QLabel("密码"))
        self.onvif_pass = QLineEdit()
        self.onvif_pass.setEchoMode(QLineEdit.Password)
        self.onvif_pass.setPlaceholderText("密码")
        creds.addWidget(self.onvif_pass, 1)
        layout.addLayout(creds)
        return page

    def _scan_onvif(self) -> None:
        self.scan_btn.setEnabled(False)
        self.onvif_status.setText("正在扫描局域网，请稍候…")
        self.onvif_table.setRowCount(0)
        self._run(
            lambda: discover_onvif(5),
            self._onvif_scanned,
            self._on_thread_error,
        )

    def _onvif_scanned(self, devices: list[OnvifDevice]) -> None:
        self.scan_btn.setEnabled(True)
        self._devices = devices or []
        self.onvif_table.setRowCount(0)
        if not devices:
            self.onvif_status.setText("未发现设备：确认摄像头已联网、与本机在同一网段")
            return
        self.onvif_status.setText(f"发现 {len(devices)} 台设备，填写账号密码后点击“添加”")
        for row, dev in enumerate(devices):
            self.onvif_table.insertRow(row)
            self.onvif_table.setItem(row, 0, QTableWidgetItem(dev.name or "ONVIF 摄像头"))
            self.onvif_table.setItem(row, 1, QTableWidgetItem(f"{dev.host}:{dev.port}"))
            status = QTableWidgetItem("● 在线")
            status.setForeground(QColor(GREEN))
            self.onvif_table.setItem(row, 2, status)
            btn = QPushButton("添加")
            btn.setObjectName("Primary")
            btn.setFixedSize(64, 26)
            btn.clicked.connect(lambda _=False, d=dev: self._add_onvif(d))
            self.onvif_table.setCellWidget(row, 3, btn)

    def _add_onvif(self, device: OnvifDevice) -> None:
        user = self.onvif_user.text().strip()
        pwd = self.onvif_pass.text()
        self.onvif_status.setText(f"正在获取 {device.host} 的 RTSP 地址…")
        self._run(
            lambda: resolve_onvif_rtsp(device, user, pwd),
            lambda uri: self._finish(CameraConfig(
                id=self.edit.id if self.edit else CameraConfig().id,
                name=device.name or "网络摄像头",
                kind="rtsp",
                source=uri,
                username=user,
                password=pwd,
            )),
            self._on_thread_error,
        )

    # ---------------- USB ----------------
    def _build_usb_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.addWidget(QLabel("设备号"))
        self.usb_index = QSpinBox()
        self.usb_index.setRange(0, 9)
        self.usb_index.setFixedWidth(70)
        self.usb_index.setStyleSheet(
            "QSpinBox { background-color: #0E1727; color: #E8F0FA; "
            "border: 1px solid #24344C; border-radius: 8px; padding: 4px 8px; }"
            "QSpinBox::up-button, QSpinBox::down-button { width: 0px; }"
        )
        top.addWidget(self.usb_index)
        self.usb_add_btn = QPushButton("添加该设备号")
        self.usb_add_btn.setObjectName("Primary")
        self.usb_add_btn.clicked.connect(self._add_usb_index)
        top.addWidget(self.usb_add_btn)
        top.addStretch(1)
        self.usb_refresh = QPushButton("刷新设备")
        self.usb_refresh.setObjectName("Ghost")
        self.usb_refresh.clicked.connect(self._scan_usb)
        top.addWidget(self.usb_refresh)
        layout.addLayout(top)

        self.usb_table = self._make_table(["设备", "分辨率", "帧率", "操作"])
        layout.addWidget(self.usb_table, 1)

        self.usb_status = QLabel("点击“刷新设备”检测本机 USB 摄像头")
        self.usb_status.setObjectName("Faint")
        layout.addWidget(self.usb_status)
        hint = QLabel("提示：摄像头被其他软件占用时可能检测不到，关闭占用程序后重试")
        hint.setObjectName("Faint")
        layout.addWidget(hint)
        return page

    def _scan_usb(self) -> None:
        self.usb_refresh.setEnabled(False)
        self.usb_status.setText("正在检测 USB 摄像头…")
        self._run(lambda: probe_usb(4), self._on_usb_scanned, self._on_thread_error)

    def _on_usb_scanned(self, devices: list[dict]) -> None:
        self.usb_refresh.setEnabled(True)
        self.usb_table.setRowCount(0)
        if not devices:
            self.usb_status.setText("未检测到 USB 摄像头，可直接输入设备号后添加")
            return
        self.usb_status.setText(f"检测到 {len(devices)} 个 USB 设备")
        for row, dev in enumerate(devices):
            self.usb_table.insertRow(row)
            self.usb_table.setItem(row, 0, QTableWidgetItem(f"USB 摄像头 #{dev['index']}"))
            self.usb_table.setItem(
                row, 1, QTableWidgetItem(f"{dev['width']} × {dev['height']}")
            )
            self.usb_table.setItem(row, 2, QTableWidgetItem(f"{dev['fps']:.0f} FPS"))
            btn = QPushButton("添加")
            btn.setObjectName("Primary")
            btn.setFixedSize(64, 26)
            btn.clicked.connect(
                lambda _=False, idx=dev["index"]: self._add_usb_index(idx)
            )
            self.usb_table.setCellWidget(row, 3, btn)

    def _add_usb_index(self, index: Optional[int] = None) -> None:
        if index is None:
            index = self.usb_index.value()
        self._finish(CameraConfig(
            id=self.edit.id if self.edit else CameraConfig().id,
            name=self.edit.name if self.edit else f"USB 摄像头 {index + 1}",
            kind="usb",
            source=str(index),
        ))

    # ---------------- RTSP ----------------
    def _build_rtsp_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(QLabel("通道名称"))
        self.rtsp_name = QLineEdit()
        self.rtsp_name.setPlaceholderText("例如：东门入口")
        layout.addWidget(self.rtsp_name)

        layout.addWidget(QLabel("RTSP 地址"))
        self.rtsp_url = QLineEdit()
        self.rtsp_url.setPlaceholderText(
            "rtsp://admin:密码@192.168.1.64:554/Streaming/Channels/101"
        )
        layout.addWidget(self.rtsp_url)

        creds = QHBoxLayout()
        creds.setSpacing(8)
        creds.addWidget(QLabel("用户名（可选）"))
        self.rtsp_user = QLineEdit()
        creds.addWidget(self.rtsp_user, 1)
        creds.addWidget(QLabel("密码（可选）"))
        self.rtsp_pass = QLineEdit()
        self.rtsp_pass.setEchoMode(QLineEdit.Password)
        creds.addWidget(self.rtsp_pass, 1)
        layout.addLayout(creds)

        test_row = QHBoxLayout()
        self.rtsp_test_btn = QPushButton("测试连接")
        self.rtsp_test_btn.setObjectName("Primary")
        self.rtsp_test_btn.clicked.connect(self._test_rtsp)
        test_row.addWidget(self.rtsp_test_btn)
        self.rtsp_status = QLabel("建议先测试连接，确认地址和账号可用")
        self.rtsp_status.setObjectName("Faint")
        test_row.addWidget(self.rtsp_status, 1)
        layout.addLayout(test_row)

        add_row = QHBoxLayout()
        add_row.addStretch(1)
        self.rtsp_add_btn = QPushButton("添加到通道")
        self.rtsp_add_btn.setObjectName("Primary")
        self.rtsp_add_btn.clicked.connect(self._add_rtsp)
        add_row.addWidget(self.rtsp_add_btn)
        layout.addLayout(add_row)
        layout.addStretch(1)
        return page

    def _test_rtsp(self) -> None:
        url = self.rtsp_url.text().strip()
        if not url:
            self.rtsp_status.setText("请先填写 RTSP 地址")
            return
        self.rtsp_test_btn.setEnabled(False)
        self.rtsp_status.setText("正在连接…")
        self._run(lambda: test_rtsp(url, 8), self._on_rtsp_tested, self._on_thread_error)

    def _on_rtsp_tested(self, result) -> None:
        self.rtsp_test_btn.setEnabled(True)
        if result.ok:
            self.rtsp_status.setText(
                f"连接成功 · {result.width}×{result.height} @ {result.fps:.0f}fps"
            )
            self.rtsp_status.setStyleSheet(f"color: {GREEN}; font-size: 11px;")
        else:
            self.rtsp_status.setText(result.message)
            self.rtsp_status.setStyleSheet(f"color: {RED}; font-size: 11px;")

    def _add_rtsp(self) -> None:
        url = self.rtsp_url.text().strip()
        if not url.lower().startswith(("rtsp://", "rtmp://", "http://")):
            QMessageBox.warning(self, "地址无效", "请填写 rtsp:// 开头的完整地址")
            return
        name = self.rtsp_name.text().strip() or "网络摄像头"
        self._finish(CameraConfig(
            id=self.edit.id if self.edit else CameraConfig().id,
            name=name,
            kind="rtsp",
            source=url,
            username=self.rtsp_user.text().strip(),
            password=self.rtsp_pass.text(),
        ))

    # ---------------- 编辑 ----------------
    def _load_edit(self, cfg: CameraConfig) -> None:
        if cfg.kind == "usb":
            self.tabs.setCurrentIndex(1)
            try:
                self.usb_index.setValue(int(cfg.source))
            except ValueError:
                pass
            self.usb_add_btn.setText("保存修改")
        else:
            self.tabs.setCurrentIndex(2)
            self.rtsp_name.setText(cfg.name)
            self.rtsp_url.setText(cfg.source)
            self.rtsp_user.setText(cfg.username)
            self.rtsp_pass.setText(cfg.password)
            self.rtsp_add_btn.setText("保存修改")

    # ---------------- 工具 ----------------
    def _make_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(False)
        table.horizontalHeader().setStyleSheet(
            "QHeaderView { background-color: #141F32; border: none; }"
            "QHeaderView::section { background-color: #141F32; color: #5E718C; "
            "border: none; border-bottom: 1px solid #24344C; padding: 8px 6px; }"
        )
        table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, len(headers)):
            table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        last = len(headers) - 1
        table.horizontalHeader().setSectionResizeMode(last, QHeaderView.Fixed)
        table.setColumnWidth(last, 92)
        table.setMinimumHeight(200)
        return table

    def _run(self, fn, on_ok, on_error) -> None:
        if self._thread is not None and self._thread.isRunning():
            return
        thread = FunctionThread(fn)
        thread.result.connect(on_ok)
        thread.error.connect(on_error)
        thread.finished.connect(lambda t=thread: self._thread_finished(t))
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        thread.start()

    def _thread_finished(self, thread) -> None:
        if self._thread is thread:
            self._thread = None

    def _on_thread_error(self, message: str) -> None:
        self.scan_btn.setEnabled(True)
        self.usb_refresh.setEnabled(True)
        self.rtsp_test_btn.setEnabled(True)
        self.onvif_status.setText(f"操作失败：{message}")
        self.onvif_status.setStyleSheet(f"color: {RED}; font-size: 11px;")
        QMessageBox.warning(self, "操作失败", message)

    def _finish(self, cfg: CameraConfig) -> None:
        self.camera_saved.emit(cfg)
        self.accept()

    def closeEvent(self, event) -> None:
        if self._thread is not None and self._thread.isRunning():
            if not self._thread.wait(2500):
                self._thread.terminate()
                self._thread.wait(500)
            self._thread = None
        super().closeEvent(event)
