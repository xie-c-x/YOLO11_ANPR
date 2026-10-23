# -*- coding: utf-8 -*-
"""车牌识别基础工具：识别、校正、裁剪、设备选择。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Tuple

import cv2
import numpy as np

PROVINCES = "京津沪渝冀晋蒙辽吉黑苏浙皖闽赣鲁豫鄂湘粤桂琼川贵云藏陕甘青宁新"
_PROVINCES = set(PROVINCES)


def resolve_device(device: Optional[str] = "auto"):
    if device not in (None, "", "auto"):
        return int(device) if str(device).isdigit() else str(device)
    try:
        import torch

        return 0 if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def crop_plate(
    frame: np.ndarray,
    box: Sequence[float],
    pad_x: float = 0.05,
    pad_y: float = 0.08,
) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = (float(v) for v in box)
    bw, bh = max(1.0, x2 - x1), max(1.0, y2 - y1)

    x1 = max(0, int(round(x1 - bw * pad_x)))
    y1 = max(0, int(round(y1 - bh * pad_y)))
    x2 = min(w, int(round(x2 + bw * pad_x)))
    y2 = min(h, int(round(y2 + bh * pad_y)))
    if x2 <= x1 or y2 <= y1:
        return np.empty((0, 0, 3), dtype=frame.dtype), (x1, y1, x2, y2)
    return frame[y1:y2, x1:x2].copy(), (x1, y1, x2, y2)


def box_iou(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = (float(v) for v in a)
    bx1, by1, bx2, by2 = (float(v) for v in b)
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


class PlateOCR:
    """RapidOCR 只跑识别（det=False），约 10~15ms/牌。"""

    def __init__(self, min_height: int = 64):
        from rapidocr_onnxruntime import RapidOCR

        self._engine = RapidOCR()
        self.min_height = int(min_height)

    def _prepare(self, crop: np.ndarray) -> np.ndarray:
        h, w = crop.shape[:2]
        if h < 1 or w < 1:
            return crop
        scale = self.min_height / float(h)
        if scale <= 1.0:
            return crop
        return cv2.resize(
            crop,
            (max(1, int(round(w * scale))), self.min_height),
            interpolation=cv2.INTER_CUBIC,
        )

    def read(self, crop: np.ndarray) -> Tuple[str, float]:
        if crop is None or crop.size == 0:
            return "", 0.0

        crop = self._prepare(crop)
        try:
            result, _ = self._engine(crop, use_det=False, use_cls=False, use_rec=True)
        except TypeError:
            result, _ = self._engine(crop)
            if not result:
                return "", 0.0
            text = "".join(str(item[1]) for item in result)
            weights = [max(1, len(str(item[1]))) for item in result]
            scores = [float(item[2]) for item in result]
            score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
            return normalize_plate(text), score

        if not result:
            return "", 0.0

        text = "".join(str(item[0]) for item in result)
        weights = [max(1, len(str(item[0]))) for item in result]
        scores = [float(item[1]) for item in result]
        score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
        return normalize_plate(text), score


def normalize_plate(text: str) -> str:
    if not text:
        return ""
    text = text.upper().strip()
    text = "".join(
        ch for ch in text if ch.isdigit() or "A" <= ch <= "Z" or ch in _PROVINCES
    )
    for i, ch in enumerate(text):
        if ch in _PROVINCES:
            text = text[i:]
            break

    chars = list(text)
    for i in range(2, len(chars)):
        if chars[i] == "O":
            chars[i] = "0"
        elif chars[i] == "I":
            chars[i] = "1"
    text = "".join(chars)
    return _trim_to_plate_window(text)


def _trim_to_plate_window(text: str) -> str:
    if len(text) <= 8:
        return text
    prefer = 8 if len(text) >= 3 and text[2] in "DF" else 7
    for size in dict.fromkeys((prefer, 8, 7)):
        for start in range(0, len(text) - size + 1):
            candidate = text[start : start + size]
            if is_plausible(candidate):
                return candidate
    return text


def is_plausible(text: str) -> bool:
    if len(text) not in (7, 8):
        return False
    if text[0] not in _PROVINCES:
        return False
    if not ("A" <= text[1] <= "Z"):
        return False
    return all(ch.isdigit() or ("A" <= ch <= "Z") for ch in text[2:])


def read_image(path: str | Path) -> Optional[np.ndarray]:
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def write_image(path: str | Path, image: np.ndarray) -> bool:
    path = Path(path)
    ext = path.suffix.lower() or ".jpg"
    ok, buffer = cv2.imencode(ext, image)
    if not ok:
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        buffer.tofile(str(path))
    except OSError:
        return False
    return True
