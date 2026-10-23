# -*- coding: utf-8 -*-
"""深色科技风主题与全局 QSS。"""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

# 与设计稿一致的调色板
BG = "#0B1220"
BG2 = "#0E1728"
SIDEBAR = "#0A101C"
TOPBAR = "#0B121F"
STATUSBAR = "#070C16"
PANEL = "#101B2E"
CARD = "#141F32"
CARD2 = "#18263D"
BORDER = "#24344C"
BORDER_SOFT = "#1C2A40"
TEXT = "#E8F0FA"
MUTED = "#8FA3BF"
FAINT = "#5E718C"
ACCENT = "#22D3A7"
ACCENT2 = "#38BDF8"
PURPLE = "#A78BFA"
GREEN = "#34D399"
AMBER = "#F59E0B"
RED = "#F87171"

QSS = f"""
* {{ outline: none; }}
QWidget {{
    color: {TEXT};
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}}
QMainWindow, QWidget#Root {{ background: {BG}; }}
QFrame#Sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
QFrame#TopBar {{ background: {TOPBAR}; border-bottom: 1px solid {BORDER}; }}
QFrame#StatusBar {{ background: {STATUSBAR}; border-top: 1px solid {BORDER}; }}

QFrame#Card, QFrame#RightPanel, QFrame#Drawer {{
    background: {CARD};
    border: 1px solid {BORDER_SOFT};
    border-radius: 14px;
}}
QFrame#Drawer {{ background: {SIDEBAR}; border-left: 1px solid {BORDER}; border-radius: 0; }}
QFrame#SubCard {{ background: {CARD2}; border: 1px solid {BORDER_SOFT}; border-radius: 10px; }}
QFrame#StatCard {{ background: {CARD}; border: 1px solid {BORDER_SOFT}; border-radius: 12px; }}
QFrame#ModalCard {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 16px; }}
QFrame#HLine {{ background: {BORDER_SOFT}; max-height: 1px; min-height: 1px; border: none; }}

QLabel {{ background: transparent; }}
QLabel#PageTitle {{ font-size: 19px; font-weight: 700; }}
QLabel#SectionTitle {{ font-size: 13px; font-weight: 700; }}
QLabel#CardTitle {{ font-size: 12px; font-weight: 700; }}
QLabel#Muted {{ color: {MUTED}; font-size: 12px; }}
QLabel#Faint {{ color: {FAINT}; font-size: 11px; }}
QLabel#Value {{ font-size: 26px; font-weight: 700; }}
QLabel#Plate {{ color: #3EFFC0; font-weight: 700; }}
QLabel#Good {{ color: {GREEN}; font-weight: 600; }}
QLabel#Bad {{ color: {RED}; font-weight: 600; }}

QPushButton {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 14px;
    color: {TEXT};
}}
QPushButton:hover {{ background: #1B2A42; }}
QPushButton:pressed {{ background: #172438; }}
QPushButton:disabled {{ color: {FAINT}; background: #101A2A; border-color: {BORDER_SOFT}; }}
QPushButton#Primary {{ background: {ACCENT}; border: none; color: #04120F; font-weight: 600; }}
QPushButton#Primary:hover {{ background: #2EE6B8; }}
QPushButton#Ghost {{ background: transparent; border: 1px solid {BORDER}; color: {MUTED}; }}
QPushButton#Ghost:hover {{ background: #18263D; color: {TEXT}; }}
QPushButton#Danger {{ background: transparent; border: none; color: {RED}; padding: 4px 8px; }}
QPushButton#Danger:hover {{ background: rgba(248, 113, 113, 0.10); }}
QPushButton#NavButton {{
    background: transparent;
    border: none;
    border-radius: 9px;
    text-align: left;
    padding-left: 44px;
    color: {MUTED};
    font-size: 13px;
}}
QPushButton#NavButton:hover {{ background: #142136; color: {TEXT}; }}
QPushButton#NavButton:checked {{
    background: rgba(34, 211, 167, 0.13);
    color: {ACCENT};
    font-weight: 600;
}}
QPushButton#IconButton {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 0;
}}
QPushButton#IconButton:hover {{ background: #1B2A42; }}

QWidget#Segmented {{ background: #0E1727; border: 1px solid {BORDER}; border-radius: 9px; }}
QPushButton#SegBtn {{
    background: transparent;
    border: none;
    border-radius: 7px;
    color: {MUTED};
    font-weight: 600;
    padding: 0;
}}
QPushButton#SegBtn:checked {{ background: {ACCENT}; color: #04120F; }}
QPushButton#SegBtn:focus {{ border: none; outline: none; }}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QAbstractSpinBox {{
    background-color: #0E1727;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: #04120F;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background: #18263D;
    border: none;
    width: 16px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {ACCENT}; }}
QLineEdit::placeholder {{ color: {FAINT}; }}
QComboBox QAbstractItemView {{
    background: {CARD};
    border: 1px solid {BORDER};
    selection-background-color: #1C2A40;
    color: {TEXT};
    outline: none;
}}
QComboBox::drop-down {{ border: none; width: 22px; }}

QTabWidget::pane {{ border: 1px solid {BORDER_SOFT}; border-radius: 10px; background: {CARD}; top: -1px; }}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    padding: 9px 18px;
    border-bottom: 2px solid transparent;
    font-weight: 600;
}}
QTabBar::tab:selected {{ color: {ACCENT}; border-bottom: 2px solid {ACCENT}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}

QTableWidget {{
    background: transparent;
    border: none;
    gridline-color: {BORDER_SOFT};
    alternate-background-color: #101B2E;
    selection-background-color: rgba(34, 211, 167, 0.12);
}}
QTableWidget::item {{ padding: 6px; border-bottom: 1px solid {BORDER_SOFT}; }}
QTableWidget::item:selected {{ background: rgba(34, 211, 167, 0.12); color: {TEXT}; }}
QHeaderView {{ background-color: {CARD}; border: none; }}
QHeaderView::section {{
    background-color: {CARD};
    color: {FAINT};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px 6px;
    font-size: 11px;
}}
QTableCornerButton::section {{ background: transparent; border: none; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2A3B57; border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: #3A5072; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; }}
QScrollBar::handle:horizontal {{ background: #2A3B57; border-radius: 4px; min-width: 28px; }}

QProgressBar {{
    background: #0E1727;
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {ACCENT2}; border-radius: 3px; }}

QToolTip {{
    background: #0E1727;
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 5px 8px;
}}
QMessageBox {{ background: {CARD}; }}
QDialog {{ background: {PANEL}; }}
QCheckBox {{ color: {MUTED}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid {BORDER}; background: #0E1727;
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QListWidget {{ background: transparent; border: none; }}
QListWidget::item {{ border-bottom: 1px solid {BORDER_SOFT}; padding: 6px; }}
QListWidget::item:selected {{ background: rgba(34, 211, 167, 0.12); }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet(QSS)
