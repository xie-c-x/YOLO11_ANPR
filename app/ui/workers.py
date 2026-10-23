# -*- coding: utf-8 -*-
"""把阻塞操作放进 QThread，避免卡住界面。"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QThread, Signal


class FunctionThread(QThread):
    result = Signal(object)
    error = Signal(str)

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            value = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
            return
        self.result.emit(value)
