# -*- coding: utf-8 -*-
"""图片车牌识别：YOLO11 检测车牌 + RapidOCR 识别车牌号。

用法：
    python scripts/anpr_predict.py                     # 默认识别 test_img/car2.jpg
    python scripts/anpr_predict.py test_img/car1.jpg    # 识别单张图片
    python scripts/anpr_predict.py test_img --no-show   # 识别整个目录

输出图片默认保存到 result_img/<原文件名>_anpr.jpg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

from plate_utils import (
    DEFAULT_IMAGE_DIR,
    DEFAULT_OUTPUT_DIR,
    PlateOCR,
    crop_plate,
    draw_plates,
    is_plausible,
    load_detector,
    read_image,
    resolve_device,
    write_image,
)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="图片车牌识别（YOLO11 检测 + RapidOCR 识别）"
    )
    parser.add_argument(
        "source",
        nargs="?",
        default=None,
        help="图片路径或图片目录；默认 test_img/car2.jpg",
    )
    parser.add_argument("--weights", default=None, help="车牌检测模型 best.pt 路径")
    parser.add_argument("--out-dir", default=None, help="结果图片保存目录，默认 result_img")
    parser.add_argument("--conf", type=float, default=0.5, help="检测置信度阈值")
    parser.add_argument("--imgsz", type=int, default=640, help="推理尺寸")
    parser.add_argument("--device", default="auto", help="auto / 0 / cpu")
    parser.add_argument("--no-show", action="store_true", help="不弹出预览窗口")
    parser.add_argument("--save-crops", default=None, help="把每个车牌小图保存到该目录")
    parser.add_argument("--debug", action="store_true", help="打印 OCR 原始信息")
    return parser.parse_args()


def collect_images(source: Path) -> list[Path]:
    if source.is_dir():
        return sorted(
            p for p in source.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS
        )
    return [source]


def detect_and_recognize(model, ocr: PlateOCR, image, args, device):
    """返回 [(xyxy, text, score), ...]。"""
    results = model.predict(
        image,
        conf=args.conf,
        imgsz=args.imgsz,
        device=device,
        verbose=False,
    )

    detections = []
    for result in results:
        for box in result.boxes:
            xyxy = box.xyxy[0].tolist()
            crop, _ = crop_plate(image, xyxy)
            text, score = ocr.read(crop)
            detections.append((xyxy, text, score))
            if args.debug:
                print(f"    bbox={[round(float(v), 1) for v in xyxy]} -> {text!r} ({score:.3f})")
    return detections


def process_image(model, ocr, image_path: Path, out_dir: Path, args, device) -> bool:
    image = read_image(image_path)
    if image is None:
        print(f"[跳过] 读不到图片：{image_path}")
        return True

    detections = detect_and_recognize(model, ocr, image, args, device)

    print(f"\n[图片] {image_path}")
    if not detections:
        print("  未检测到车牌")
    else:
        for i, (box, text, score) in enumerate(detections, 1):
            flag = "OK" if is_plausible(text) else "格式存疑"
            shown = text or "未识别"
            x1, y1, x2, y2 = (int(round(float(v))) for v in box)
            print(
                f"  #{i} {shown:<10s} 置信度 {score:.3f}  [{flag}]  "
                f"bbox=({x1},{y1},{x2},{y2})"
            )

    # 先保存车牌小图，再画框，避免小图上也带着绿框
    if args.save_crops and detections:
        crop_dir = Path(args.save_crops)
        crop_dir.mkdir(parents=True, exist_ok=True)
        for i, (box, text, _) in enumerate(detections, 1):
            crop, _ = crop_plate(image, box, pad_x=0.0, pad_y=0.0)
            safe = "".join(ch for ch in (text or "plate") if ch.isalnum()) or "plate"
            write_image(crop_dir / f"{image_path.stem}_{i}_{safe}.jpg", crop)

    draw_plates(image, detections)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{image_path.stem}_anpr.jpg"
    if not write_image(out_path, image):
        print(f"  [错误] 结果图片保存失败：{out_path}")
        return False
    print(f"  已保存：{out_path}")

    if not args.no_show:
        cv2.imshow("ANPR - Image", image)
        print("  按任意键继续，按 q/ESC 退出预览...")
        key = cv2.waitKey(0) & 0xFF
        if key in (27, ord("q")):
            return False
    return True


def main() -> int:
    args = parse_args()

    source = Path(args.source) if args.source else (DEFAULT_IMAGE_DIR / "car2.jpg")
    if not source.exists():
        print(f"[错误] 找不到输入路径：{source}")
        return 2

    images = collect_images(source)
    if not images:
        print(f"[错误] 目录里没有图片：{source}")
        return 2

    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUTPUT_DIR

    try:
        model = load_detector(args.weights)
        ocr = PlateOCR()
    except (FileNotFoundError, ImportError, RuntimeError) as exc:
        print(f"[错误] {exc}")
        return 2

    device = resolve_device(args.device)
    print(f"设备：{device}    图片数：{len(images)}")

    keep_going = True
    for image_path in images:
        if not keep_going:
            break
        keep_going = process_image(model, ocr, image_path, out_dir, args, device)

    if not args.no_show:
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
