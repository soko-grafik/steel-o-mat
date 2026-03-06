from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover - runtime dependency
    cv2 = None  # type: ignore[assignment]


@dataclass(slots=True)
class CameraReading:
    name: str
    frame: Any
    pixel_tip: tuple[int, int] | None
    board_tip_mm: tuple[float, float] | None


class CameraStream:
    def __init__(self, name: str, index: int, homography: list[list[float]] | None) -> None:
        if cv2 is None:
            raise RuntimeError("opencv-python is required. Install requirements.txt first.")
        self.name = name
        self.index = index
        self.homography = None if homography is None else np.array(homography, dtype=np.float32)
        self.capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not self.capture.isOpened():
            raise RuntimeError(f"Unable to open camera index {index} ({name}).")
        self.background_gray: np.ndarray | None = None

    def close(self) -> None:
        self.capture.release()

    def grab_background(self) -> None:
        ok, frame = self.capture.read()
        if not ok:
            raise RuntimeError(f"Could not read background frame from camera '{self.name}'.")
        self.background_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    def _detect_tip_pixel(self, frame: Any) -> tuple[int, int] | None:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.background_gray is None:
            self.background_gray = gray
            return None

        diff = cv2.absdiff(gray, self.background_gray)
        _, mask = cv2.threshold(diff, 35, 255, cv2.THRESH_BINARY)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.dilate(mask, kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(contour) < 20:
            return None

        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            return None
        cx = int(moments["m10"] / moments["m00"])
        cy = int(moments["m01"] / moments["m00"])

        points = contour.reshape(-1, 2)
        distances = np.sum((points - np.array([cx, cy])) ** 2, axis=1)
        tip = points[int(np.argmax(distances))]
        return int(tip[0]), int(tip[1])

    def _project_to_board(self, tip_px: tuple[int, int] | None) -> tuple[float, float] | None:
        if tip_px is None or self.homography is None:
            return None
        src = np.array([[[float(tip_px[0]), float(tip_px[1])]]], dtype=np.float32)
        dst = cv2.perspectiveTransform(src, self.homography)
        return float(dst[0, 0, 0]), float(dst[0, 0, 1])

    def read(self) -> CameraReading:
        ok, frame = self.capture.read()
        if not ok:
            raise RuntimeError(f"Could not read frame from camera '{self.name}'.")
        tip_px = self._detect_tip_pixel(frame)
        tip_mm = self._project_to_board(tip_px)
        return CameraReading(self.name, frame, tip_px, tip_mm)
