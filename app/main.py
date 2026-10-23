# -*- coding: utf-8 -*-
"""ANPR 桌面应用入口。"""

from __future__ import annotations

import ctypes
import os
import sys
import traceback
from pathlib import Path

os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|stimeout;5000000",
)

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from app.config import APP_NAME, APP_TITLE, DATA_DIR, VERSION
from app.theme import apply_theme
from app.ui.icons import app_icon
from app.ui.main_window import MainWindow


def _install_excepthook() -> None:
    def hook(exc_type, exc_value, exc_tb):
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            log = DATA_DIR / "logs" / "error.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as f:
                f.write(text + "\n")
        except OSError:
            pass
        QMessageBox.critical(None, "程序异常", text[-1500:])

    sys.excepthook = hook


def main() -> int:
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                f"ANPR.Desktop.{VERSION}"
            )
        except Exception:
            pass

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_TITLE)
    app.setApplicationVersion(VERSION)
    app.setWindowIcon(app_icon())
    apply_theme(app)
    _install_excepthook()

    window = MainWindow()
    window.show()

    # 开发 / 打包验证用：设置 ANPR_SCREENSHOT 后定时截图并退出
    shot_path = os.environ.get("ANPR_SCREENSHOT")
    if shot_path:
        if os.environ.get("ANPR_HIDDEN") == "1":
            window.move(-3000, -3000)
        delay = int(os.environ.get("ANPR_SCREENSHOT_DELAY", "25000"))

        def capture() -> None:
            try:
                window.grab().save(shot_path)
            finally:
                window.close()
                app.quit()

        QTimer.singleShot(delay, capture)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
