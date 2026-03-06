from __future__ import annotations

import argparse
import json
import random
import threading
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .camera import CameraStream
from .config import load_config
from .fusion import fuse_points
from .runtime import RuntimeState
from .scoring import score_point


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Steel dart scorer web UI (PWA)")
    parser.add_argument("--config", default="config/cameras.json", help="Path to camera JSON config")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8080, help="Bind port")
    parser.add_argument("--demo", action="store_true", help="Run without camera pipeline")
    return parser.parse_args()


def _camera_worker(runtime: RuntimeState, stop_event: threading.Event, config_path: str) -> None:
    cfg = load_config(config_path)
    streams: list[CameraStream] = []
    try:
        for cam in cfg.cameras:
            if not cam.enabled:
                continue
            streams.append(CameraStream(cam.name, cam.index, cam.homography))

        if not streams:
            return

        for stream in streams:
            stream.grab_background()

        while not stop_event.is_set():
            points: list[tuple[float, float]] = []
            for stream in streams:
                reading = stream.read()
                if reading.board_tip_mm is not None:
                    points.append(reading.board_tip_mm)

            fused = fuse_points(points, cfg.vote_threshold_mm)
            if fused is not None:
                result = score_point(fused[0], fused[1])
                runtime.update_from_result(result, fused[0], fused[1], source="camera")
            time.sleep(0.03)
    finally:
        for stream in streams:
            stream.close()


def _make_handler(runtime: RuntimeState, root: Path, config_path: str) -> type[SimpleHTTPRequestHandler]:
    config_file = Path(config_path)

    def read_camera_config() -> dict[str, Any]:
        if not config_file.exists():
            return {"vote_threshold_mm": 25.0, "cameras": []}
        return json.loads(config_file.read_text(encoding="utf-8"))

    def validate_camera_config(payload: dict[str, Any]) -> dict[str, Any]:
        vote_threshold = float(payload.get("vote_threshold_mm", 25.0))
        raw_cameras = payload.get("cameras", [])
        if not isinstance(raw_cameras, list):
            raise ValueError("cameras must be an array")

        cameras: list[dict[str, Any]] = []
        for camera in raw_cameras[:4]:
            if not isinstance(camera, dict):
                continue
            index = int(camera.get("index", 0))
            raw_name = str(camera.get("name", "")).strip()
            cameras.append(
                {
                    "name": raw_name or f"cam-{index}",
                    "index": index,
                    "enabled": bool(camera.get("enabled", True)),
                    "homography": camera.get("homography"),
                }
            )

        return {"vote_threshold_mm": vote_threshold, "cameras": cameras}

    def list_usb_cameras(max_devices: int = 10) -> list[dict[str, Any]]:
        try:
            import cv2
        except ImportError:
            return []

        devices: list[dict[str, Any]] = []
        for index in range(max_devices):
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(index)
            if not cap.isOpened():
                cap.release()
                continue
            ok, _ = cap.read()
            cap.release()
            if ok:
                devices.append({"index": index, "label": f"USB Camera {index}"})
        return devices

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(root), **kwargs)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            body = self.rfile.read(length)
            return json.loads(body.decode("utf-8"))

        def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_jpeg(self, image_data: bytes, status: HTTPStatus = HTTPStatus.OK) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(image_data)))
            self.end_headers()
            self.wfile.write(image_data)

        def _stream_mjpeg(self, index: int) -> None:
            try:
                import cv2
            except ImportError:
                self._send_json({"ok": False, "error": "opencv not installed"}, status=HTTPStatus.SERVICE_UNAVAILABLE)
                return

            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(index)
            if not cap.isOpened():
                cap.release()
                self._send_json({"ok": False, "error": f"camera {index} not available"}, status=HTTPStatus.NOT_FOUND)
                return

            boundary = "frame"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={boundary}")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

            try:
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        time.sleep(0.03)
                        continue
                    ok, encoded = cv2.imencode(".jpg", frame)
                    if not ok:
                        continue
                    jpg = encoded.tobytes()
                    self.wfile.write(f"--{boundary}\r\n".encode("utf-8"))
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(jpg)}\r\n\r\n".encode("utf-8"))
                    self.wfile.write(jpg)
                    self.wfile.write(b"\r\n")
                    time.sleep(0.04)
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                cap.release()

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)

            if path == "/api/state":
                self._send_json(runtime.snapshot())
                return
            if path == "/api/game":
                self._send_json(runtime.game_snapshot())
                return
            if path == "/api/match":
                state = runtime.snapshot()
                self._send_json(
                    {
                        "game": state["game"],
                        "match": state["match"],
                        "players": state["players"],
                        "current_player": state["current_player"],
                    }
                )
                return
            if path == "/api/history":
                state = runtime.snapshot()
                self._send_json({"history": state["history"]})
                return
            if path == "/api/stats":
                state = runtime.snapshot()
                self._send_json({"stats": state["stats"]})
                return
            if path == "/api/camera-config":
                self._send_json(read_camera_config())
                return
            if path == "/api/cameras":
                self._send_json({"cameras": list_usb_cameras()})
                return
            if path == "/api/camera-preview":
                try:
                    index = int((query.get("index") or ["0"])[0])
                except ValueError:
                    self._send_json({"ok": False, "error": "invalid camera index"}, status=HTTPStatus.BAD_REQUEST)
                    return

                try:
                    import cv2
                except ImportError:
                    self._send_json({"ok": False, "error": "opencv not installed"}, status=HTTPStatus.SERVICE_UNAVAILABLE)
                    return

                cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
                if not cap.isOpened():
                    cap.release()
                    self._send_json({"ok": False, "error": f"camera {index} not available"}, status=HTTPStatus.NOT_FOUND)
                    return
                ok, frame = cap.read()
                cap.release()
                if not ok:
                    self._send_json({"ok": False, "error": f"failed reading camera {index}"}, status=HTTPStatus.BAD_GATEWAY)
                    return
                ok, encoded = cv2.imencode(".jpg", frame)
                if not ok:
                    self._send_json({"ok": False, "error": "failed encoding preview"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                    return
                self._send_jpeg(encoded.tobytes())
                return
            if path == "/api/camera-stream":
                try:
                    index = int((query.get("index") or ["0"])[0])
                except ValueError:
                    self._send_json({"ok": False, "error": "invalid camera index"}, status=HTTPStatus.BAD_REQUEST)
                    return
                self._stream_mjpeg(index)
                return
            if path == "/healthz":
                self._send_json({"ok": True})
                return
            return super().do_GET()

        def do_POST(self) -> None:  # noqa: N802
            if self.path == "/api/game":
                data = self._read_json()
                try:
                    game = str(data.get("game", "501"))
                    variations = data.get("variations", [])
                    if not isinstance(variations, list):
                        raise ValueError("variations must be an array")
                    updated = runtime.set_game(game=game, variations=[str(v) for v in variations])
                    self._send_json({"ok": True, "game": updated})
                except ValueError as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return

            if self.path == "/api/match":
                data = self._read_json()
                try:
                    raw_players = data.get("players", [])
                    if not isinstance(raw_players, list):
                        raise ValueError("players must be an array")
                    players = [str(p) for p in raw_players]
                    legs_to_win_set = int(data.get("legs_to_win_set", 3))
                    updated = runtime.set_players(players, legs_to_win_set=legs_to_win_set)
                    self._send_json({"ok": True, **updated})
                except ValueError as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return

            if self.path == "/api/undo":
                result = runtime.undo_last_action()
                if not result["ok"]:
                    self._send_json(result, status=HTTPStatus.BAD_REQUEST)
                    return
                self._send_json(result)
                return

            if self.path == "/api/manual":
                data = self._read_json()
                try:
                    points = int(data.get("points"))
                    bed = str(data.get("bed", "S"))
                    runtime.update_manual(points=points, bed=bed, source="manual")
                    self._send_json({"ok": True, "state": runtime.snapshot()})
                except (TypeError, ValueError):
                    self._send_json({"ok": False, "error": "points must be an integer"}, status=HTTPStatus.BAD_REQUEST)
                return

            if self.path == "/api/camera-config":
                data = self._read_json()
                try:
                    normalized = validate_camera_config(data)
                    config_file.parent.mkdir(parents=True, exist_ok=True)
                    config_file.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
                    self._send_json({"ok": True, "config": normalized})
                except (TypeError, ValueError) as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return

            if self.path == "/api/simulate":
                data = self._read_json()
                if "x_mm" in data and "y_mm" in data:
                    result = runtime.update_from_point(float(data["x_mm"]), float(data["y_mm"]), source="simulate")
                    self._send_json({"ok": True, "result": {"points": result.points, "bed": result.bed}})
                    return

                x_mm = random.uniform(-160.0, 160.0)
                y_mm = random.uniform(-160.0, 160.0)
                result = runtime.update_from_point(x_mm, y_mm, source="simulate")
                self._send_json({"ok": True, "result": {"points": result.points, "bed": result.bed}, "state": runtime.snapshot()})
                return

            self._send_json({"error": "Not Found"}, status=HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def main() -> int:
    args = parse_args()
    runtime = RuntimeState()

    stop_event = threading.Event()
    worker: threading.Thread | None = None
    if not args.demo:
        worker = threading.Thread(
            target=_camera_worker,
            args=(runtime, stop_event, args.config),
            daemon=True,
            name="camera-worker",
        )
        worker.start()

    web_root = Path(__file__).resolve().parents[2] / "web"
    handler = _make_handler(runtime, web_root, args.config)
    server = ThreadingHTTPServer((args.host, args.port), handler)

    print(f"Web UI running at http://{args.host}:{args.port}")
    print("PWA install available in supported browsers.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        stop_event.set()
        if worker is not None:
            worker.join(timeout=1.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
