# -*- coding: utf-8 -*-
"""摄像头/视频实时车牌识别：YOLO11 检测车牌 + RapidOCR 识别车牌号。

用法：
    python scripts/anpr_full.py                    # 默认摄像头 0
    python scripts/anpr_full.py 1                  # 第二个摄像头
    python scripts/anpr_full.py test.mp4           # 识别视频文件
    python scripts/anpr_full.py --no-show --max-frames 100 --save-video result_img/demo.mp4

预览窗口里按 q 或 ESC 退出。
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np

from plate_utils import (
    PlateOCR,
    box_iou,
    crop_plate,
    draw_plates,
    is_plausible,
    load_detector,
    resolve_device,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="摄像头/视频实时车牌识别（YOLO11 + RapidOCR）"
    )
    parser.add_argument(
        "source",
        nargs="?",
        default="0",
        help="摄像头编号（0、1...）或视频文件路径，默认 0",
    )
    parser.add_argument("--weights", default=None, help="车牌检测模型 best.pt 路径")
    parser.add_argument("--conf", type=float, default=0.5, help="检测置信度阈值")
    parser.add_argument("--imgsz", type=int, default=640, help="推理尺寸，画面大/车牌小可调 960")
    parser.add_argument("--device", default="auto", help="auto / 0 / cpu")
    parser.add_argument("--width", type=int, default=0, help="请求的宽度，0=使用摄像头默认值")
    parser.add_argument("--height", type=int, default=0, help="请求的高度，0=使用摄像头默认值")
    parser.add_argument(
        "--ocr-every",
        type=int,
        default=1,
        help="每隔多少帧重新识别一次（1=每帧；CPU 慢可设 2~3）",
    )
    parser.add_argument("--save-video", default=None, help="把带标注的画面录成 mp4")
    parser.add_argument("--no-show", action="store_true", help="不弹出预览窗口")
    parser.add_argument("--max-frames", type=int, default=0, help="最多处理多少帧，0=不限")
    return parser.parse_args()


def open_source(source: str, width: int, height: int):
    """打开摄像头或视频，返回 (cap, 是否摄像头)。"""
    if source.isdigit():
        index = int(source)
        backends = (
            # 实测 Windows 下 MSMF 通常比 DirectShow 帧率高（这台机器 30fps vs 10fps），
            # 所以优先 MSMF；打不开再依次回退。
            (cv2.CAP_MSMF, "MediaFoundation"),
            (cv2.CAP_DSHOW, "DirectShow"),
            (cv2.CAP_ANY, "默认后端"),
        )
        for backend, name in backends:
            cap = cv2.VideoCapture(index, backend)
            if not cap.isOpened():
                cap.release()
                continue
            # 不强制分辨率：摄像头默认分辨率通常帧率最高；需要更高清时再传 --width/--height
            if width > 0:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            if height > 0:
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ok, frame = cap.read()
            if ok and frame is not None:
                print(
                    f"摄像头 {index} 已打开（{name}），"
                    f"实际分辨率 {frame.shape[1]}x{frame.shape[0]}"
                )
                return cap, True
            cap.release()
        raise RuntimeError(
            f"无法打开摄像头 {index}。请检查：\n"
            "  1) 摄像头是否被其他软件（相机/会议软件）占用；\n"
            "  2) Windows 设置 → 隐私 → 相机，是否允许桌面应用访问；\n"
            "  3) 设备管理器里摄像头是否正常。"
        )

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"找不到视频文件：{path}")
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频：{path}")
    print(f"视频已打开：{path}")
    return cap, False


def main() -> int:
    args = parse_args()

    try:
        model = load_detector(args.weights)
        ocr = PlateOCR()
        cap, is_camera = open_source(args.source, args.width, args.height)
    except (FileNotFoundError, ImportError, RuntimeError) as exc:
        print(f"[错误] {exc}")
        return 2

    device = resolve_device(args.device)
    print(f"设备：{device}    按 q/ESC 退出" if not args.no_show else f"设备：{device}")

    src_fps = cap.get(cv2.CAP_PROP_FPS)
    if not src_fps or src_fps != src_fps:  # 摄像头通常返回 0 或 NaN
        src_fps = 30.0 if is_camera else 25.0

    tracks: list[dict] = []
    max_age = 5             # 车牌消失后最多再保留几帧，防止框闪烁
    ocr_every = max(1, args.ocr_every)

    fps_hist: deque[float] = deque(maxlen=30)
    writer = None
    writer_failed = False
    frame_idx = 0
    read_failures = 0
    seen_plates: set[str] = set()

    try:
        while True:
            loop_start = time.perf_counter()
            ok, frame = cap.read()
            if not ok or frame is None:
                if is_camera and read_failures < 30:
                    read_failures += 1
                    time.sleep(0.03)
                    continue
                break
            read_failures = 0
            frame_idx += 1

            # 摄像头返回的 frame 是驱动缓冲区的视图，直接送进 YOLO 会慢十几倍
            # （实测 250ms vs 34ms），先复制成独立、连续的数组。
            frame = np.ascontiguousarray(frame)

            # 1) YOLO 检测
            result = model.predict(
                frame,
                conf=args.conf,
                imgsz=args.imgsz,
                device=device,
                verbose=False,
            )[0]

            # 2) 跨帧匹配 + OCR
            detections = []
            for box in result.boxes:
                xyxy = box.xyxy[0].tolist()

                # 和上一帧的车牌框做 IoU 匹配，避免每帧都重新识别
                matched = None
                best_iou = 0.5
                for track in tracks:
                    iou = box_iou(xyxy, track["box"])
                    if iou > best_iou:
                        matched, best_iou = track, iou

                is_new = matched is None
                if is_new:
                    matched = {"box": xyxy, "text": "", "score": 0.0, "last_seen": frame_idx}
                    tracks.append(matched)
                else:
                    matched["box"] = xyxy
                    matched["last_seen"] = frame_idx

                # 新车牌立刻识别；老车牌按 ocr_every 间隔更新
                if is_new or frame_idx % ocr_every == 0:
                    crop, _ = crop_plate(frame, xyxy)
                    if crop.shape[0] >= 16 and crop.shape[1] >= 32:
                        text, score = ocr.read(crop)
                        # 已经识别出合法车牌时，不让后续的坏读数覆盖它
                        if text and score >= 0.5 and (is_plausible(text) or not matched["text"]):
                            matched["text"] = text
                            matched["score"] = score
                            seen_plates.add(text)

                detections.append((matched["box"], matched["text"], matched["score"]))

            # 3) 清理已经消失的车牌
            tracks = [t for t in tracks if frame_idx - t["last_seen"] <= max_age]

            # 4) 画框、写中文车牌号
            draw_plates(frame, detections)

            # 5) FPS 和提示
            fps = 1.0 / max(1e-6, time.perf_counter() - loop_start)
            fps_hist.append(fps)
            avg_fps = sum(fps_hist) / len(fps_hist)
            cv2.putText(
                frame,
                f"FPS {avg_fps:5.1f}   plates {len(detections)}",
                (12, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )

            # 6) 录制
            if args.save_video and not writer_failed:
                if writer is None:
                    out_path = Path(args.save_video)
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    h, w = frame.shape[:2]
                    writer = cv2.VideoWriter(
                        str(out_path),
                        cv2.VideoWriter_fourcc(*"mp4v"),
                        src_fps,
                        (w, h),
                    )
                    if not writer.isOpened():
                        print(f"[警告] 无法创建视频文件：{out_path}，本次不录制")
                        writer_failed = True
                        writer = None
                    else:
                        print(f"开始录制：{out_path}（{src_fps:.0f} FPS）")
                if writer is not None:
                    writer.write(frame)

            # 7) 显示 / 退出
            if not args.no_show:
                cv2.imshow("ANPR - Camera", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break

            if args.max_frames and frame_idx >= args.max_frames:
                break

    except KeyboardInterrupt:
        print("\n用户中断")
    finally:
        cap.release()
        if writer is not None:
            writer.release()
        if not args.no_show:
            cv2.destroyAllWindows()

    print(f"\n处理完成：{frame_idx} 帧")
    if fps_hist:
        print(f"平均帧率：{sum(fps_hist) / len(fps_hist):.1f} FPS")
    if seen_plates:
        print("识别到的车牌：" + "、".join(sorted(seen_plates)))
    else:
        print("没有识别到车牌")
    return 0


if __name__ == "__main__":
    sys.exit(main())
