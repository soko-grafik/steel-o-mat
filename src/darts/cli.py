from __future__ import annotations

import argparse
import sys

import numpy as np

from .camera import CameraStream
from .config import load_config
from .fusion import fuse_points
from .scoring import score_point


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Steel dart auto scoring from 3 USB cameras")
    parser.add_argument("--config", default="config/cameras.json", help="Path to JSON camera config")
    parser.add_argument("--headless", action="store_true", help="Run without cv2 preview windows")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)

    try:
        import cv2
    except ImportError:
        print("opencv-python is required. Install requirements.txt first.", file=sys.stderr)
        return 1

    streams: list[CameraStream] = []
    for cam in cfg.cameras:
        if not cam.enabled:
            continue
        streams.append(CameraStream(cam.name, cam.index, cam.homography))

    if not streams:
        print("No enabled cameras in config.", file=sys.stderr)
        return 1

    for stream in streams:
        stream.grab_background()

    print("Started. Press 'b' to refresh background, 'q' to quit.")

    try:
        while True:
            readings = [s.read() for s in streams]
            points = [r.board_tip_mm for r in readings if r.board_tip_mm is not None]
            fused = fuse_points(points, cfg.vote_threshold_mm)

            score_text = "No dart detected"
            if fused is not None:
                result = score_point(fused[0], fused[1])
                score_text = f"{result.points} ({result.bed}) @ ({fused[0]:.1f}, {fused[1]:.1f})mm"

            if not args.headless:
                for reading in readings:
                    frame = reading.frame
                    if reading.pixel_tip is not None:
                        cv2.circle(frame, reading.pixel_tip, 6, (0, 255, 0), 2)
                    cv2.putText(frame, reading.name, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                    cv2.putText(frame, score_text, (10, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                    cv2.imshow(f"Darts - {reading.name}", frame)

                board = np.zeros((600, 600, 3), dtype=np.uint8)
                cv2.circle(board, (300, 300), 170, (100, 100, 100), 2)
                cv2.circle(board, (300, 300), 162, (100, 100, 100), 2)
                cv2.circle(board, (300, 300), 107, (100, 100, 100), 2)
                cv2.circle(board, (300, 300), 99, (100, 100, 100), 2)
                cv2.circle(board, (300, 300), 16, (100, 100, 100), 2)
                cv2.circle(board, (300, 300), 6, (100, 100, 100), 2)
                if fused is not None:
                    px = int(300 + fused[0])
                    py = int(300 - fused[1])
                    cv2.circle(board, (px, py), 6, (0, 255, 255), -1)
                cv2.putText(board, score_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
                cv2.imshow("Board (mm)", board)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("b"):
                for stream in streams:
                    stream.grab_background()
                print("Background refreshed.")
    finally:
        for stream in streams:
            stream.close()
        if not args.headless:
            cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
