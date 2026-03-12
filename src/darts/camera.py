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
    frame: Any | None
    pixel_tip: tuple[int, int] | None
    board_tip_mm: tuple[float, float] | None


def open_video_capture(index: int, width: int = 640, height: int = 480, fps: int = 30) -> Any:
    """Helper to open VideoCapture with fallbacks for Windows backends."""
    if cv2 is None:
        # Return something that mimics a closed capture if cv2 is missing
        class DummyCapture:
            def isOpened(self) -> bool: return False
            def release(self) -> None: pass
        return DummyCapture()

    def apply_settings(c: Any) -> Any:
        for prop, value in (
            (cv2.CAP_PROP_FRAME_WIDTH, width),
            (cv2.CAP_PROP_FRAME_HEIGHT, height),
            (cv2.CAP_PROP_FPS, fps),
        ):
            try:
                c.set(prop, value)
            except Exception:
                # Some camera drivers/backends throw opaque OpenCV C++ exceptions here.
                # Keep capture open and continue with whatever defaults are supported.
                pass
        return c

    def try_backend(*args: Any) -> Any:
        try:
            return cv2.VideoCapture(*args)
        except Exception:
            class DummyCapture:
                def isOpened(self) -> bool: return False
                def release(self) -> None: pass
            return DummyCapture()

    def safe_is_opened(c: Any) -> bool:
        try:
            return bool(c.isOpened())
        except Exception:
            return False

    def safe_release(c: Any) -> None:
        try:
            c.release()
        except Exception:
            pass

    # Try DSHOW first (fastest on Windows)
    cap = try_backend(index, cv2.CAP_DSHOW)
    if safe_is_opened(cap):
        return apply_settings(cap)
    safe_release(cap)

    # Try MSMF (modern Windows)
    cap = try_backend(index, cv2.CAP_MSMF)
    if safe_is_opened(cap):
        return apply_settings(cap)
    safe_release(cap)

    # Default backend
    cap = try_backend(index)
    return apply_settings(cap)


class CameraStream:
    def __init__(
        self,
        name: str,
        index: int,
        homography: list[list[float]] | None,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        demo_image_path: str | None = None,
    ) -> None:
        if cv2 is None:
            raise RuntimeError("opencv-python is required. Install requirements.txt first.")
        self.name = name
        self.index = index
        self.homography = None if homography is None else np.array(homography, dtype=np.float32)
        self.demo_image_path = demo_image_path
        
        if self.demo_image_path:
            self.capture = None
        else:
            self.capture = open_video_capture(index, width, height, fps)
            try:
                opened = bool(self.capture.isOpened())
            except Exception:
                opened = False
            if not opened:
                raise RuntimeError(f"Unable to open camera index {index} ({name}).")
        self.width = width
        self.height = height
        self.fps = fps
        self._read_failures = 0
        
        self.background_gray: np.ndarray | None = None

    def close(self) -> None:
        if self.capture:
            self.capture.release()

    def grab_background(self) -> None:
        if self.demo_image_path:
            frame = cv2.imread(self.demo_image_path)
            if frame is None:
                raise RuntimeError(f"Could not read demo image from {self.demo_image_path}")
        else:
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
        if self.demo_image_path:
            frame = cv2.imread(self.demo_image_path)
            if frame is None:
                raise RuntimeError(f"Could not read demo image from {self.demo_image_path}")
        else:
            try:
                ok, frame = self.capture.read()
            except Exception:
                ok, frame = False, None

            if not ok or frame is None:
                self._read_failures += 1

                # Attempt a soft reconnect after repeated failures.
                if self._read_failures >= 5:
                    try:
                        self.capture.release()
                    except Exception:
                        pass
                    self.capture = open_video_capture(self.index, self.width, self.height, self.fps)
                    self._read_failures = 0

                return CameraReading(self.name, None, None, None)

            self._read_failures = 0

        tip_px = self._detect_tip_pixel(frame)
        tip_mm = self._project_to_board(tip_px)
        return CameraReading(self.name, frame, tip_px, tip_mm)
