# -*- coding: utf-8 -*-
"""车牌识别公共工具：模型加载、裁剪、OCR、中文绘制、车牌校正。

anpr_predict.py（图片）和 anpr_full.py（摄像头）共用这里的实现，
避免两份脚本各写一套、改一处漏一处。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ----------------------------- 路径 -----------------------------
SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
DEFAULT_WEIGHTS = SCRIPTS_DIR / "runs" / "detect" / "train" / "weights" / "best.pt"
DEFAULT_IMAGE_DIR = PROJECT_ROOT / "test_img"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "result_img"

# ----------------------------- 车牌规则 -----------------------------
PROVINCES = "京津沪渝冀晋蒙辽吉黑苏浙皖闽赣鲁豫鄂湘粤桂琼川贵云藏陕甘青宁新"
_PROVINCE_SET = set(PROVINCES)

# Windows 自带中文字体，按优先级尝试
_FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/msyh.ttc"),      # 微软雅黑
    Path("C:/Windows/Fonts/msyhbd.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),    # 黑体
    Path("C:/Windows/Fonts/simsun.ttc"),    # 宋体
)
_FONT_CACHE: dict[int, ImageFont.FreeTypeFont] = {}


def resolve_device(device: Optional[str] = "auto"):
    """把 auto/0/cpu 统一成 ultralytics 能接受的 device 参数。"""
    if device not in (None, "", "auto"):
        return int(device) if str(device).isdigit() else str(device)
    try:
        import torch

        return 0 if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def load_detector(weights: Optional[str | Path] = None):
    """加载 YOLO 车牌检测模型。"""
    from ultralytics import YOLO

    path = Path(weights) if weights else DEFAULT_WEIGHTS
    if not path.exists():
        raise FileNotFoundError(
            f"找不到车牌检测模型：{path}\n"
            f"请把训练好的 best.pt 放到该位置（不需要重新训练）。"
        )
    return YOLO(str(path))


def crop_plate(
    frame: np.ndarray,
    box: Sequence[float],
    pad_x: float = 0.05,
    pad_y: float = 0.08,
) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    """按检测框裁剪车牌，并向外扩一点边，避免把车牌边缘切掉。"""
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
    """两个 xyxy 框的 IoU，用于摄像头模式下跨帧匹配同一块车牌。"""
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


def read_image(path: str | Path) -> Optional[np.ndarray]:
    """支持中文路径的图片读取（cv2.imread 在 Windows 下遇到中文路径会返回 None）。"""
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def write_image(path: str | Path, image: np.ndarray) -> bool:
    """支持中文路径的图片保存。"""
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


class PlateOCR:
    """RapidOCR 封装：只跑识别（det=False），不要对车牌小图再跑文本检测。

    RapidOCR 默认会先做文本检测再做识别，对一张已经裁好的车牌图，
    这一步既慢（约 0.6s）又容易把车牌切成多段；只用识别约 13ms。
    """

    def __init__(self, min_height: int = 64):
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:
            raise ImportError(
                "未安装 rapidocr-onnxruntime。请在本项目的 conda 环境执行：\n"
                "  python -m pip install rapidocr-onnxruntime"
            ) from exc
        self._engine = RapidOCR()
        self.min_height = int(min_height)

    def _prepare(self, crop: np.ndarray) -> np.ndarray:
        """小图放大到至少 min_height，识别率会明显提高。"""
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
        """返回 (校正后的车牌号, 置信度)。识别失败返回 ("", 0.0)。"""
        if crop is None or crop.size == 0:
            return "", 0.0

        crop = self._prepare(crop)
        try:
            result, _ = self._engine(
                crop, use_det=False, use_cls=False, use_rec=True
            )
        except TypeError:
            # 兼容老版本 rapidocr：退回完整流程，结果格式是 [box, text, score]
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
    """清掉分隔点/空格/杂字，并修正常见的 O/0、I/1 误识别。

    注意：
    - 省份汉字和发牌机关字母（第 2 位）保持原样，不能把 Q 改成 0，
      因为 Q 是合法字母（例如 京Q）；第 2 位也不会出现 O/I。
    - 从第 3 位开始才是“字母+数字”混合，O/I 不用于中国车牌，
      所以这里的 O→0、I→1 是安全的。
    - 检测框偏大时，OCR 可能把车牌两侧的车身/边框读成杂字（例如多出一个 F），
      所以最后会尝试截取一个合法的 7/8 位车牌窗口。
    """
    if not text:
        return ""

    text = text.upper().strip()
    text = "".join(
        ch for ch in text if ch.isdigit() or "A" <= ch <= "Z" or ch in _PROVINCE_SET
    )

    # 只保留从省份开始的部分，丢掉车牌左侧读出来的杂字
    for i, ch in enumerate(text):
        if ch in _PROVINCE_SET:
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
    """OCR 多读出一两位时，截出一个合法的 7/8 位车牌。"""
    if len(text) <= 8:
        return text

    # 新能源小型车第 3 位通常是 D/F，优先按 8 位截取；否则优先普通 7 位牌
    prefer = 8 if len(text) >= 3 and text[2] in "DF" else 7
    for size in dict.fromkeys((prefer, 8, 7)):
        for start in range(0, len(text) - size + 1):
            candidate = text[start : start + size]
            if is_plausible(candidate):
                return candidate
    return text


def is_plausible(text: str) -> bool:
    """粗略校验是否符合中国车牌格式（7 位普通牌 / 8 位新能源牌）。"""
    if len(text) not in (7, 8):
        return False
    if text[0] not in _PROVINCE_SET:
        return False
    if not ("A" <= text[1] <= "Z"):
        return False
    return all(ch.isdigit() or ("A" <= ch <= "Z") for ch in text[2:])


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    size = max(10, int(size))
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]

    font = None
    for path in _FONT_CANDIDATES:
        if path.exists():
            try:
                font = ImageFont.truetype(str(path), size)
                break
            except OSError:
                continue
    if font is None:
        try:
            font = ImageFont.load_default(size=size)
        except TypeError:  # Pillow < 10.1
            font = ImageFont.load_default()

    _FONT_CACHE[size] = font
    return font


def draw_plates(
    image: np.ndarray,
    detections: Iterable[Tuple[Sequence[float], str, float]],
) -> np.ndarray:
    """在原图上画框和车牌文字，返回同一张图。

    cv2.putText 不支持中文，会显示成 "???", 所以文字用 PIL 绘制。
    detections: [(xyxy, plate_text, ocr_score), ...]
    """
    detections = list(detections)
    if not detections:
        return image

    h_img, w_img = image.shape[:2]

    def clamp_box(box):
        x1, y1, x2, y2 = (int(round(float(v))) for v in box)
        x1, x2 = max(0, min(x1, w_img - 1)), max(0, min(x2, w_img - 1))
        y1, y2 = max(0, min(y1, h_img - 1)), max(0, min(y2, h_img - 1))
        return x1, y1, x2, y2

    for box, _, _ in detections:
        x1, y1, x2, y2 = clamp_box(box)
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)

    pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)

    for box, text, score in detections:
        x1, y1, x2, y2 = clamp_box(box)
        text = text or "未识别"
        label = f"{text}  {score:.2f}" if text != "未识别" else text

        size = int(max(16, min(40, (y2 - y1) * 0.6)))
        font = _load_font(size)

        # anchor="lt" = 左上角对齐，方便算背景框
        left, top, right, bottom = draw.textbbox((0, 0), label, font=font, anchor="lt")
        tw, th = right - left, bottom - top

        tx = max(2, min(x1, w_img - tw - 8))
        ty = y1 - th - 10
        if ty < 2:
            ty = min(y2 + 6, h_img - th - 4)
        ty = max(2, ty)

        draw.rectangle(
            [tx - 4, ty - 2, tx + tw + 4, ty + th + 2],
            fill=(0, 0, 0),
        )
        color = (0, 255, 0) if is_plausible(text) else (0, 200, 255)
        draw.text((tx, ty), label, font=font, fill=color, anchor="lt")

    image[:] = cv2.cvtColor(np.asarray(pil_img), cv2.COLOR_RGB2BGR)
    return image
