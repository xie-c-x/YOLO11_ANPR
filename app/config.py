# -*- coding: utf-8 -*-
"""应用配置、路径与数据模型。"""

from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_NAME = "ANPR"
APP_TITLE = "ANPR 智能车牌识别"
VERSION = "1.0.0"


def app_root() -> Path:
    """开发态为项目根目录；打包后为 exe 所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", app_root()))
    return base.joinpath(*parts)


def choose_data_dir() -> Path:
    root = app_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".anpr_write_test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return root
    except OSError:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "ANPR"
        base.mkdir(parents=True, exist_ok=True)
        return base


DATA_DIR = choose_data_dir()
CONFIG_DIR = DATA_DIR / "config"
LOG_DIR = DATA_DIR / "logs"
CAPTURE_DIR = DATA_DIR / "captures"
CONFIG_PATH = CONFIG_DIR / "cameras.json"

MAX_CAMERAS = 4


def default_weights() -> Path:
    candidates = [
        resource_path("models", "best.pt"),
        resource_path("scripts", "runs", "detect", "train", "weights", "best.pt"),
        app_root() / "scripts" / "runs" / "detect" / "train" / "weights" / "best.pt",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def onvif_wsdl_dir() -> Path | None:
    bundled = resource_path("wsdl")
    if bundled.exists():
        return bundled
    try:
        import onvif  # noqa: F401

        local = Path(onvif.__file__).resolve().parent.parent / "wsdl"
        if local.exists():
            return local
    except Exception:
        pass
    return None


@dataclass
class CameraConfig:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = "摄像头"
    kind: str = "usb"  # usb / rtsp
    source: str = "0"  # USB: "0"; RTSP: full url
    username: str = ""
    password: str = ""
    enabled: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CameraConfig":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:8]),
            name=str(data.get("name") or "摄像头"),
            kind="rtsp" if str(data.get("kind", "usb")).lower() == "rtsp" else "usb",
            source=str(data.get("source", "0")),
            username=str(data.get("username", "")),
            password=str(data.get("password", "")),
            enabled=bool(data.get("enabled", True)),
        )

    @property
    def label(self) -> str:
        return self.name or "摄像头"


@dataclass
class AppConfig:
    channels: list[CameraConfig] = field(default_factory=list)
    enabled_count: int = 1
    auto_reconnect: bool = True
    save_snapshots: bool = True
    autostart_monitor: bool = True
    conf: float = 0.5
    imgsz: int = 640

    @classmethod
    def default(cls) -> "AppConfig":
        return cls(
            channels=[CameraConfig(name="摄像头 1", kind="usb", source="0")],
            enabled_count=1,
        )

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "AppConfig":
        if not path.exists():
            cfg = cls.default()
            cfg.save(path)
            return cfg
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cfg = cls.default()
            cfg.save(path)
            return cfg

        channels = [CameraConfig.from_dict(item) for item in raw.get("channels", [])
                    if isinstance(item, dict)]
        if not channels:
            channels = [CameraConfig(name="摄像头 1", kind="usb", source="0")]
        channels = channels[:MAX_CAMERAS]

        cfg = cls(
            channels=channels,
            enabled_count=max(1, min(MAX_CAMERAS, int(raw.get("enabled_count", 1)))),
            auto_reconnect=bool(raw.get("auto_reconnect", True)),
            save_snapshots=bool(raw.get("save_snapshots", True)),
            autostart_monitor=bool(raw.get("autostart_monitor", True)),
            conf=max(0.1, min(0.95, float(raw.get("conf", 0.5)))),
            imgsz=int(raw.get("imgsz", 640)),
        )
        return cfg

    def save(self, path: Path = CONFIG_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "enabled_count": int(self.enabled_count),
            "auto_reconnect": bool(self.auto_reconnect),
            "save_snapshots": bool(self.save_snapshots),
            "autostart_monitor": bool(self.autostart_monitor),
            "conf": float(self.conf),
            "imgsz": int(self.imgsz),
            "channels": [c.to_dict() for c in self.channels],
        }
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
