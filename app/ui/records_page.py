# -*- coding: utf-8 -*-
"""识别记录页：读取本地 CSV 并按关键字筛选。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config import LOG_DIR
from ..theme import FAINT, GREEN, MUTED, RED, TEXT


class RecordsPage(QWidget):
    def __init__(self, recorder, parent=None):
        super().__init__(parent)
        self.recorder = recorder
        self._rows: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("识别记录")
        title.setObjectName("PageTitle")
        titles.addWidget(title)
        sub = QLabel(f"历史记录保存在 {LOG_DIR}")
        sub.setObjectName("Muted")
        titles.addWidget(sub)
        header.addLayout(titles)
        header.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索车牌 / 摄像头")
        self.search.setFixedWidth(220)
        self.search.textChanged.connect(self._filter)
        header.addWidget(self.search)
        refresh = QPushButton("刷新")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        root.addLayout(header)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["时间", "摄像头", "车牌号", "置信度"])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setStyleSheet(
            "QHeaderView { background-color: #141F32; border: none; }"
            "QHeaderView::section { background-color: #141F32; color: #5E718C; "
            "border: none; border-bottom: 1px solid #24344C; padding: 8px 6px; }"
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for col in range(1, 4):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        card_layout.addWidget(self.table)
        root.addWidget(card, 1)

        self.empty = QLabel("暂无记录，识别到车牌后会自动写入")
        self.empty.setObjectName("Faint")
        self.empty.setAlignment(Qt.AlignCenter)
        root.addWidget(self.empty)
        self.refresh()

    def refresh(self) -> None:
        self._rows = self.recorder.load_today()
        self._rows.reverse()
        self._filter()

    def _filter(self) -> None:
        keyword = self.search.text().strip().lower()
        rows = [
            row for row in self._rows
            if not keyword
            or keyword in str(row.get("车牌号", "")).lower()
            or keyword in str(row.get("摄像头", "")).lower()
        ]
        self.table.setRowCount(0)
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(row.get("时间", ""))))
            self.table.setItem(r, 1, QTableWidgetItem(str(row.get("摄像头", ""))))
            plate = QTableWidgetItem(str(row.get("车牌号", "")))
            plate.setForeground(QColor(GREEN))
            self.table.setItem(r, 2, plate)
            self.table.setItem(r, 3, QTableWidgetItem(str(row.get("置信度", ""))))
        self.empty.setVisible(not rows)
        self.table.setVisible(bool(rows))

    def showEvent(self, event) -> None:
        self.refresh()
        super().showEvent(event)
