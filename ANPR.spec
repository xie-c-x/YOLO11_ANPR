# -*- mode: python ; coding: utf-8 -*-
# ANPR 桌面端打包配置（文件夹版，无控制台窗口）
# 重新打包：pyinstaller ANPR.spec --noconfirm
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH)
ENV_SITE = Path(r"C:\Users\11037\.conda\envs\yolo11_anpr\Lib\site-packages")

datas = [
    (str(ROOT / "scripts" / "runs" / "detect" / "train" / "weights" / "best.pt"), "models"),
    (str(ENV_SITE / "wsdl"), "wsdl"),
]
binaries = []
hiddenimports = []
hiddenimports += collect_submodules("zeep")

for package in (
    "ultralytics",
    "rapidocr_onnxruntime",
    "onnxruntime",
    "onvif",
    "wsdiscovery",
):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["run.py"],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "paddle", "paddleocr", "paddlepaddle", "tensorflow",
        "IPython", "pytest", "tkinter", "PyQt5", "PyQt6",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ANPR",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(ROOT / "assets" / "app.ico")],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ANPR",
)
