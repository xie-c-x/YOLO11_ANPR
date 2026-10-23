# -*- coding: utf-8 -*-
"""ANPR 环境自检：确认解释器、依赖、GPU、模型、数据集是否就绪。

用法：
    python scripts/check_env.py

退出码：0=正常，1=有警告但可运行，2=有致命问题。
"""

from __future__ import annotations

import importlib.metadata as md
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEIGHTS = ROOT / "scripts" / "runs" / "detect" / "train" / "weights" / "best.pt"
DATASET = ROOT / "plate_dataset"
PLATE_YAML = ROOT / "plate.yaml"

REQUIRED = {
    "ultralytics": "ultralytics",
    "torch": "torch",
    "numpy": "numpy",
    "Pillow": "PIL",
    "opencv-python": "cv2",
    "rapidocr-onnxruntime": "rapidocr_onnxruntime",
    "onnxruntime": "onnxruntime",
}


def pkg_version(name: str) -> str | None:
    try:
        return md.version(name)
    except md.PackageNotFoundError:
        return None


def major(version: str | None) -> int:
    if not version:
        return -1
    try:
        return int(version.split(".")[0])
    except ValueError:
        return -1


def main() -> int:
    warnings: list[str] = []
    errors: list[str] = []

    print("=" * 68)
    print(" ANPR 环境自检")
    print("=" * 68)
    print(f"Python : {sys.version.split()[0]}")
    print(f"解释器 : {sys.executable}")

    if "yolo11_anpr" not in sys.executable.lower():
        expected = Path.home() / ".conda" / "envs" / "yolo11_anpr" / "python.exe"
        warnings.append(
            "当前不是项目的 yolo11_anpr 环境。建议使用：\n"
            f"    {expected} scripts\\anpr_predict.py"
        )

    # ---------------- 依赖 ----------------
    print("\n[依赖版本]")
    for dist_name, import_name in REQUIRED.items():
        version = pkg_version(dist_name)
        if version is None:
            errors.append(f"缺少依赖：{dist_name}")
            print(f"  {dist_name:<24s} 未安装  <-- 缺少")
        else:
            print(f"  {dist_name:<24s} {version}")
            try:
                __import__(import_name)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{dist_name} 已安装但导入失败：{exc}")

    # ---------------- OpenCV 重复安装 ----------------
    opencv_pkgs = {
        name: pkg_version(name)
        for name in (
            "opencv-python",
            "opencv-contrib-python",
            "opencv-python-headless",
            "opencv-contrib-python-headless",
        )
        if pkg_version(name)
    }
    if len(opencv_pkgs) > 1:
        detail = "、".join(f"{k}=={v}" for k, v in opencv_pkgs.items())
        warnings.append(
            f"同时安装了多个 OpenCV 包：{detail}\n"
            "    它们会互相覆盖 cv2，容易出现 imshow/视频读写异常。只保留一个即可。"
        )

    # ---------------- PaddleOCR 版本冲突 ----------------
    paddle = pkg_version("paddlepaddle")
    paddleocr = pkg_version("paddleocr")
    if paddle and paddleocr:
        if major(paddleocr) < 3 and major(paddle) >= 3:
            warnings.append(
                f"paddleocr {paddleocr} 与 paddlepaddle {paddle} 不兼容。\n"
                "    旧版 PaddleOCR 在 Paddle 3.x 下会报 fused_conv2d / OneDnnContext 错误。\n"
                "    本项目的两个脚本已改用 RapidOCR，不再依赖 Paddle；"
                "如果不用 Paddle 可以卸载：\n"
                "      python -m pip uninstall -y paddleocr paddlepaddle"
            )

    # ---------------- CUDA ----------------
    print("\n[GPU]")
    try:
        import torch

        cuda_ok = torch.cuda.is_available()
        print(f"  torch {torch.__version__}  CUDA 可用: {cuda_ok}")
        if cuda_ok:
            print(f"  GPU: {torch.cuda.get_device_name(0)}")
        else:
            warnings.append("CUDA 不可用，将用 CPU 推理（速度会慢 2~3 倍）。")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"torch 无法使用：{exc}")
        print(f"  torch 导入失败：{exc}")

    # ---------------- 模型 ----------------
    print("\n[模型]")
    if WEIGHTS.exists():
        print(f"  OK  {WEIGHTS}  ({WEIGHTS.stat().st_size / 1024 / 1024:.1f} MB)")
    else:
        errors.append(f"找不到检测模型：{WEIGHTS}")
        print(f"  缺失 {WEIGHTS}")

    # ---------------- 数据集 ----------------
    print("\n[数据集]")
    if not PLATE_YAML.exists():
        warnings.append(f"找不到数据集配置：{PLATE_YAML}")
    else:
        print(f"  OK  {PLATE_YAML}")
    for split in ("train", "val", "test"):
        img_dir = DATASET / "images" / split
        lbl_dir = DATASET / "labels" / split
        if not img_dir.exists():
            continue
        n_img = len(list(img_dir.glob("*.jpg"))) + len(list(img_dir.glob("*.png")))
        n_lbl = len(list(lbl_dir.glob("*.txt"))) if lbl_dir.exists() else 0
        mark = "OK " if n_img and n_img == n_lbl else "!! "
        print(f"  {mark}{split:<5s} images={n_img:<5d} labels={n_lbl}")
        if n_img != n_lbl:
            warnings.append(f"{split} 图片和标签数量不一致：{n_img} vs {n_lbl}")

    # ---------------- 中文字体 ----------------
    print("\n[中文字体]")
    font_ok = any(
        Path(p).exists()
        for p in (
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\simhei.ttf",
            r"C:\Windows\Fonts\simsun.ttc",
        )
    )
    print("  OK  找到中文字体" if font_ok else "  !!  没找到中文字体，车牌汉字会显示异常")
    if not font_ok:
        warnings.append("缺少中文字体（msyh.ttc/simhei.ttf/simsun.ttc）")

    # ---------------- RapidOCR 快速验证 ----------------
    print("\n[RapidOCR]")
    try:
        from rapidocr_onnxruntime import RapidOCR  # noqa: F401

        print("  OK  rapidocr_onnxruntime 可导入")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"RapidOCR 导入失败：{exc}")
        print(f"  !!  导入失败：{exc}")

    # ---------------- 汇总 ----------------
    print("\n" + "=" * 68)
    if warnings:
        print("警告：")
        for item in warnings:
            print(f"  - {item}")
    if errors:
        print("致命问题：")
        for item in errors:
            print(f"  - {item}")
        print("\n结论：环境未就绪")
        return 2
    if warnings:
        print("\n结论：可以运行，但建议处理上面的警告")
        return 1

    print("结论：环境正常")
    print("\n下一步：")
    print("  python scripts/anpr_predict.py --no-show        # 图片识别")
    print("  python scripts/anpr_full.py                     # 摄像头实时识别")
    print("  python scripts/anpr_full.py --no-show --max-frames 100 --save-video result_img/demo.mp4")
    return 0


if __name__ == "__main__":
    sys.exit(main())
