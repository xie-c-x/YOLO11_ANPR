# -*- coding: utf-8 -*-
"""车牌事件记录：CSV、截图。"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from ..config import CAPTURE_DIR, LOG_DIR
from .plate import write_image


@dataclass
class PlateEvent:
    cam_id: str
    cam_name: str
    plate: str
    conf: float
    box: tuple[int, int, int, int]
    timestamp: datetime
    crop: Optional[np.ndarray] = None


class Recorder:
    def __init__(self, save_snapshots: bool = True):
        self.save_snapshots = save_snapshots
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        self._session_count = 0

    @property
    def session_count(self) -> int:
        return self._session_count

    def csv_path(self, day: Optional[datetime] = None) -> Path:
        day = day or datetime.now()
        return LOG_DIR / f"plates_{day:%Y%m%d}.csv"

    def log(self, event: PlateEvent) -> bool:
        path = self.csv_path(event.timestamp)
        new_file = not path.exists()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                if new_file:
                    writer.writerow(["时间", "摄像头", "车牌号", "置信度", "检测框"])
                writer.writerow([
                    event.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    event.cam_name,
                    event.plate,
                    f"{event.conf:.3f}",
                    f"{event.box[0]},{event.box[1]},{event.box[2]},{event.box[3]}",
                ])
        except OSError:
            return False

        self._session_count += 1
        if self.save_snapshots and event.crop is not None and event.crop.size:
            day_dir = CAPTURE_DIR / event.timestamp.strftime("%Y%m%d")
            filename = (
                f"{event.plate}_{event.timestamp:%H%M%S}_"
                f"{event.cam_id}.jpg"
            )
            write_image(day_dir / filename, event.crop)
        return True

    def load_today(self) -> list[dict]:
        return self.load_file(self.csv_path())

    def load_file(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        rows: list[dict] = []
        try:
            with path.open("r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(row)
        except (OSError, csv.Error):
            return []
        return rows

    def history_files(self) -> list[Path]:
        try:
            return sorted(LOG_DIR.glob("plates_*.csv"), reverse=True)
        except OSError:
            return []
