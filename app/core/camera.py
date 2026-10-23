# -*- coding: utf-8 -*-
"""摄像头采集、单实例推理调度与车牌事件。"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from urllib.parse import quote

os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|stimeout;5000000",
)

import cv2
import numpy as np
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QImage

from ..config import CameraConfig
from .engine import ANPREngine, Detection
from .plate import crop_plate, is_plausible
from .recorder import PlateEvent


@dataclass
class CameraState:
    cfg: CameraConfig
    online: bool = False
    message: str = "未启动"
    seq: int = 0
    processed_seq: int = 0
    frame: Optional[np.ndarray] = None
    last_infer: float = 0.0
    fps: float = 0.0
    last_frame_time: float = 0.0


def build_rtsp_url(cfg: CameraConfig) -> str:
    url = cfg.source.strip()
    if cfg.username and "://" in url and "@" not in url:
        scheme, rest = url.split("://", 1)
        user = quote(cfg.username, safe="")
        pwd = quote(cfg.password, safe="")
        url = f"{scheme}://{user}:{pwd}@{rest}"
    return url


def _open_capture(cfg: CameraConfig) -> tuple[Optional[cv2.VideoCapture], str]:
    if cfg.kind == "usb":
        try:
            index = int(cfg.source)
        except ValueError:
            return None, "USB 设备号无效"

        for backend, name in (
            (cv2.CAP_MSMF, "MediaFoundation"),
            (cv2.CAP_DSHOW, "DirectShow"),
            (cv2.CAP_ANY, "默认后端"),
        ):
            cap = cv2.VideoCapture(index, backend)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                ok, frame = cap.read()
                if ok and frame is not None:
                    return cap, f"USB {index} · {name}"
            cap.release()
        return None, f"无法打开 USB 摄像头 {index}"

    url = build_rtsp_url(cfg)
    last_error = ""
    for backend, name in ((cv2.CAP_FFMPEG, "FFmpeg"), (cv2.CAP_ANY, "默认后端")):
        cap = cv2.VideoCapture(url, backend)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ok, frame = cap.read()
            if ok and frame is not None:
                return cap, f"RTSP · {name}"
            last_error = "已连接但读取不到画面"
        cap.release()
    return None, last_error or "RTSP 连接失败"


class CaptureThread(QThread):
    def __init__(self, cfg: CameraConfig, manager: "CameraManager"):
        super().__init__()
        self.cfg = cfg
        self.manager = manager
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            cap, message = _open_capture(self.cfg)
            if cap is None:
                self.manager.set_status(self.cfg.id, False, message)
                if not self.manager.auto_reconnect:
                    return
                self._stop.wait(2.0)
                continue

            self.manager.set_status(self.cfg.id, True, message)
            failures = 0
            frames = 0
            fps_start = time.monotonic()
            is_live = self.cfg.source.lower().startswith(
                ("rtsp://", "rtmp://", "http://", "https://")
            )
            src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
            frame_interval = 0.0 if (is_live or src_fps <= 1) else 1.0 / src_fps
            next_frame_at = time.monotonic()
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    failures += 1
                    if failures >= 20:
                        break
                    self._stop.wait(0.04)
                    continue

                failures = 0
                if frame_interval:
                    next_frame_at += frame_interval
                    delay = next_frame_at - time.monotonic()
                    if delay > 0:
                        self._stop.wait(delay)
                frame = np.ascontiguousarray(frame)
                self.manager.push_frame(self.cfg, frame)
                frames += 1
                now = time.monotonic()
                if now - fps_start >= 1.0:
                    self.manager.set_fps(self.cfg.id, frames / (now - fps_start))
                    frames = 0
                    fps_start = now

            cap.release()
            if not self._stop.is_set():
                self.manager.set_status(self.cfg.id, False, "连接中断，正在重连")
                if not self.manager.auto_reconnect:
                    return
                self._stop.wait(1.5)


class InferenceThread(QThread):
    def __init__(self, manager: "CameraManager"):
        super().__init__()
        self.manager = manager
        self._stop = threading.Event()
        self._last_event: dict[str, tuple[str, float]] = {}

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            job = self.manager.take_job()
            if job is None:
                self._stop.wait(0.01)
                continue

            cam_id, frame, seq, state = job
            started = time.perf_counter()
            try:
                detections = self.manager.engine.detect(frame)
            except Exception as exc:  # noqa: BLE001
                self.manager.set_status(cam_id, True, f"识别失败：{exc}")
                self.manager.mark_processed(cam_id, seq)
                continue

            latency = (time.perf_counter() - started) * 1000
            self.manager.mark_processed(cam_id, seq)
            self.manager.results_ready.emit(cam_id, detections, latency)

            best = next(
                (d for d in detections if d.text and d.conf >= 0.45 and is_plausible(d.text)),
                None,
            )
            if best is None:
                best = next((d for d in detections if d.text and d.conf >= 0.6), None)
            if best is not None:
                self._emit_plate(state.cfg, frame, best)

    def _emit_plate(self, cfg: CameraConfig, frame: np.ndarray, det: Detection) -> None:
        now = time.monotonic()
        last = self._last_event.get(cfg.id)
        if last and last[0] == det.text and now - last[1] < 6.0:
            return
        self._last_event[cfg.id] = (det.text, now)
        crop, _ = crop_plate(frame, det.box, pad_x=0.10, pad_y=0.16)
        event = PlateEvent(
            cam_id=cfg.id,
            cam_name=cfg.label,
            plate=det.text,
            conf=det.conf,
            box=det.box,
            timestamp=datetime.now(),
            crop=crop,
        )
        self.manager.plate_event.emit(event)
        self.manager.set_last_plate(cfg.id, det.text, det.conf)


class CameraManager(QObject):
    frame_ready = Signal(str, object)          # cam_id, QImage
    results_ready = Signal(str, object, float)  # cam_id, list[Detection], latency
    status_changed = Signal(str, bool, str)    # cam_id, online, message
    fps_updated = Signal(str, float)
    plate_event = Signal(object)               # PlateEvent
    last_plate_changed = Signal(str, str, float)

    def __init__(self, engine: ANPREngine, auto_reconnect: bool = True):
        super().__init__()
        self.engine = engine
        self.auto_reconnect = auto_reconnect
        self._lock = threading.Lock()
        self.states: dict[str, CameraState] = {}
        self._captures: dict[str, CaptureThread] = {}
        self._inference: Optional[InferenceThread] = None
        self._order: list[str] = []
        self._rr = 0
        self._last_plates: dict[str, tuple[str, float]] = {}

    # ---------------- 生命周期 ----------------
    def start(self, channels: list[CameraConfig], enabled_count: int) -> None:
        self.stop()
        self.states.clear()
        self._order.clear()
        active = channels[: max(1, min(len(channels), enabled_count))]
        for cfg in active:
            if not cfg.enabled:
                continue
            self.states[cfg.id] = CameraState(cfg=cfg)
            self._order.append(cfg.id)

        self._inference = InferenceThread(self)
        self._inference.start()
        for cam_id, state in self.states.items():
            thread = CaptureThread(state.cfg, self)
            self._captures[cam_id] = thread
            thread.start()

    def stop(self) -> None:
        for thread in list(self._captures.values()):
            thread.stop()
        for thread in list(self._captures.values()):
            if not thread.wait(2000):
                thread.terminate()
                thread.wait(500)
        self._captures.clear()

        if self._inference is not None:
            self._inference.stop()
            if not self._inference.wait(3000):
                self._inference.terminate()
                self._inference.wait(500)
            self._inference = None

        with self._lock:
            self.states.clear()
            self._order.clear()

    def reconnect(self, cam_id: str) -> None:
        with self._lock:
            state = self.states.get(cam_id)
        if state is None:
            return
        old = self._captures.pop(cam_id, None)
        if old is not None:
            old.stop()
            old.wait(1200)
        thread = CaptureThread(state.cfg, self)
        self._captures[cam_id] = thread
        thread.start()

    # ---------------- 采集线程调用 ----------------
    def push_frame(self, cfg: CameraConfig, frame: np.ndarray) -> None:
        with self._lock:
            state = self.states.get(cfg.id)
            if state is None:
                return
            state.frame = frame
            state.seq += 1
            state.last_frame_time = time.monotonic()
            h, w = frame.shape[:2]
            qimg = QImage(
                frame.data, w, h, frame.strides[0], QImage.Format.Format_BGR888
            ).copy()
        self.frame_ready.emit(cfg.id, qimg)

    def set_status(self, cam_id: str, online: bool, message: str) -> None:
        with self._lock:
            state = self.states.get(cam_id)
            if state is None:
                return
            state.online = online
            state.message = message
        self.status_changed.emit(cam_id, online, message)

    def set_fps(self, cam_id: str, fps: float) -> None:
        with self._lock:
            state = self.states.get(cam_id)
        if state is not None:
            state.fps = fps
        self.fps_updated.emit(cam_id, fps)

    # ---------------- 推理线程调用 ----------------
    def take_job(self):
        now = time.monotonic()
        with self._lock:
            if not self._order:
                return None
            n = len(self._order)
            for offset in range(n):
                cam_id = self._order[(self._rr + offset) % n]
                state = self.states.get(cam_id)
                if state is None or not state.online or state.frame is None:
                    continue
                if state.seq <= state.processed_seq:
                    continue
                if now - state.last_infer < 0.09:
                    continue
                state.last_infer = now
                self._rr = (self._rr + offset + 1) % n
                return cam_id, state.frame.copy(), state.seq, state
        return None

    def mark_processed(self, cam_id: str, seq: int) -> None:
        with self._lock:
            state = self.states.get(cam_id)
            if state is not None:
                state.processed_seq = max(state.processed_seq, seq)

    def set_last_plate(self, cam_id: str, plate: str, conf: float) -> None:
        self._last_plates[cam_id] = (plate, conf)
        self.last_plate_changed.emit(cam_id, plate, conf)

    def get_last_plate(self, cam_id: str) -> tuple[str, float]:
        return self._last_plates.get(cam_id, ("", 0.0))

    def online_count(self) -> int:
        with self._lock:
            return sum(1 for s in self.states.values() if s.online)

    def state_snapshot(self) -> dict[str, CameraState]:
        with self._lock:
            return dict(self.states)
