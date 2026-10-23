# -*- coding: utf-8 -*-
"""USB / RTSP / ONVIF 设备探测与地址解析。"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

import cv2

from ..config import onvif_wsdl_dir


@dataclass
class OnvifDevice:
    xaddr: str
    host: str
    port: int
    name: str
    manufacturer: str = ""


@dataclass
class ProbeResult:
    ok: bool
    message: str
    width: int = 0
    height: int = 0
    fps: float = 0.0
    url: str = ""


def onvif_available() -> bool:
    try:
        import onvif  # noqa: F401
        import wsdiscovery  # noqa: F401

        return True
    except Exception:
        return False


def _scope_value(scope, key: str) -> str:
    text = str(getattr(scope, "value", scope))
    prefix = f"onvif://www.onvif.org/{key}/"
    if text.startswith(prefix):
        return unquote(text[len(prefix):])
    return ""


def discover_onvif(timeout: int = 4) -> list[OnvifDevice]:
    """WS-Discovery 扫描同一网段的 ONVIF 设备。"""
    try:
        from wsdiscovery import QName
        from wsdiscovery.discovery import ThreadedWSDiscovery
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"ONVIF 依赖未安装：{exc}") from exc

    wsd = ThreadedWSDiscovery()
    wsd.start()
    try:
        services = wsd.searchServices(
            types=[QName("http://www.onvif.org/ver10/network/wsdl", "NetworkVideoTransmitter")],
            timeout=timeout,
        )
    finally:
        try:
            wsd.stop()
        except Exception:
            pass

    devices: dict[str, OnvifDevice] = {}
    for service in services:
        scopes = service.getScopes() or []
        name = ""
        manufacturer = ""
        for scope in scopes:
            name = name or _scope_value(scope, "name")
            manufacturer = manufacturer or _scope_value(scope, "hardware") or _scope_value(scope, "manufacturer")
        for xaddr in service.getXAddrs():
            parsed = urlparse(xaddr)
            host = parsed.hostname or ""
            if not host or host in devices:
                continue
            devices[host] = OnvifDevice(
                xaddr=xaddr,
                host=host,
                port=parsed.port or 80,
                name=name or host,
                manufacturer=manufacturer,
            )
    return list(devices.values())


def resolve_onvif_rtsp(
    device: OnvifDevice,
    username: str,
    password: str,
    prefer_substream: bool = False,
) -> str:
    """通过 ONVIF Media 服务取 RTSP 地址。"""
    try:
        from onvif import ONVIFCamera
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"onvif-zeep 未安装：{exc}") from exc

    wsdl = onvif_wsdl_dir()
    kwargs = {"wsdl_dir": str(wsdl)} if wsdl else {}
    camera = ONVIFCamera(device.host, device.port, username, password, **kwargs)
    media = camera.create_media_service()
    profiles = media.GetProfiles()
    if not profiles:
        raise RuntimeError("摄像头没有返回媒体配置（Profile）")
    profile = profiles[-1] if prefer_substream and len(profiles) > 1 else profiles[0]
    request = {
        "StreamSetup": {
            "Stream": "RTP-Unicast",
            "Transport": {"Protocol": "RTSP"},
        },
        "ProfileToken": profile.token,
    }
    uri = media.GetStreamUri(request)
    result = str(getattr(uri, "Uri", "") or "")
    if not result:
        raise RuntimeError("摄像头没有返回 RTSP 地址")
    return result


def test_rtsp(url: str, timeout: float = 8.0) -> ProbeResult:
    started = time.monotonic()
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        while time.monotonic() - started < timeout:
            ok, frame = cap.read()
            if ok and frame is not None:
                h, w = frame.shape[:2]
                fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
                return ProbeResult(True, "连接成功", w, h, fps, url)
            time.sleep(0.05)
        return ProbeResult(False, "连接超时，请检查地址/账号/网络")
    finally:
        cap.release()


def probe_usb(max_index: int = 4) -> list[dict]:
    """快速列出 USB 摄像头。

    DSHOW 按索引枚举最稳定；MSMF 在部分 OpenCV 版本里无法按索引打开。
    只检测前 4 个索引，避免对话框等待过久。
    """
    found: list[dict] = []
    for index in range(max_index):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(index, cv2.CAP_MSMF)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ok, frame = cap.read()
            if ok and frame is not None:
                h, w = frame.shape[:2]
                fps = float(cap.get(cv2.CAP_PROP_FPS) or 0) or 30.0
                found.append({
                    "index": index,
                    "width": w,
                    "height": h,
                    "fps": fps,
                    "source": str(index),
                })
        cap.release()
    return found
