# -*- coding: utf-8 -*-
"""YOLO11 检测 + RapidOCR 识别的线程安全封装。"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .plate import PlateOCR, crop_plate, resolve_device


@dataclass
class Detection:
    box: tuple[int, int, int, int]
    text: str
    conf: float

    @property
    def width(self) -> int:
        return max(0, self.box[2] - self.box[0])

    @property
    def height(self) -> int:
        return max(0, self.box[3] - self.box[1])


class ANPREngine:
    def __init__(
        self,
        weights: str | Path,
        device: str = "auto",
        imgsz: int = 640,
        conf: float = 0.5,
    ):
        from ultralytics import YOLO

        self.weights = str(weights)
        self.device = resolve_device(device)
        self.imgsz = int(imgsz)
        self.conf = float(conf)
        self._lock = threading.RLock()
        self.model = YOLO(self.weights)
        self.ocr = PlateOCR()
        self._warmup()

    def _warmup(self) -> None:
        dummy = np.zeros((480, 640, 3), dtype=np.uint8)
        with self._lock:
            try:
                self.model.predict(
                    dummy,
                    conf=self.conf,
                    imgsz=self.imgsz,
                    device=self.device,
                    verbose=False,
                )
            except Exception:
                # warmup 失败不影响正式推理，正式推理时再暴露具体错误
                pass

    @property
    def device_name(self) -> str:
        try:
            import torch

            if isinstance(self.device, int) and torch.cuda.is_available():
                return torch.cuda.get_device_name(self.device)
        except Exception:
            pass
        if self.device == "cpu":
            return "CPU"
        return str(self.device)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        if frame is None or frame.size == 0:
            return []
        if frame.ndim == 2:
            frame = np.stack([frame] * 3, axis=-1)

        with self._lock:
            results = self.model.predict(
                frame,
                conf=self.conf,
                imgsz=self.imgsz,
                device=self.device,
                verbose=False,
            )
            detections: list[Detection] = []
            if not results:
                return detections
            for box in results[0].boxes:
                xyxy = box.xyxy[0].tolist()
                score = float(box.conf[0])
                crop, _ = crop_plate(frame, xyxy)
                text, ocr_score = self.ocr.read(crop)
                x1, y1, x2, y2 = (int(round(float(v))) for v in xyxy)
                detections.append(
                    Detection(
                        box=(x1, y1, x2, y2),
                        text=text,
                        conf=ocr_score if ocr_score > 0 else score,
                    )
                )
        detections.sort(key=lambda d: d.conf, reverse=True)
        return detections
