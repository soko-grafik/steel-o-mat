from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class CameraConfig:
    name: str
    index: int
    enabled: bool = True
    homography: list[list[float]] | None = None


@dataclass(slots=True)
class SystemConfig:
    cameras: list[CameraConfig]
    vote_threshold_mm: float = 25.0
    width: int = 640
    height: int = 480
    fps: int = 30


def _parse_camera(raw: dict[str, Any]) -> CameraConfig:
    return CameraConfig(
        name=str(raw["name"]),
        index=int(raw["index"]),
        enabled=bool(raw.get("enabled", True)),
        homography=raw.get("homography"),
    )


def load_config(path: str | Path) -> SystemConfig:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    cameras = [_parse_camera(item) for item in data["cameras"]]
    return SystemConfig(
        cameras=cameras,
        vote_threshold_mm=float(data.get("vote_threshold_mm", 25.0)),
        width=int(data.get("width", 640)),
        height=int(data.get("height", 480)),
        fps=int(data.get("fps", 30)),
    )
