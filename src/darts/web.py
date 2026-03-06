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


def _make_handler(runtime: RuntimeState, root: Path) -> type[SimpleHTTPRequestHandler]:
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

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/api/state":
                self._send_json(runtime.snapshot())
                return
            if self.path == "/api/game":
                self._send_json(runtime.game_snapshot())
                return
            if self.path == "/api/match":
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
            if self.path == "/api/history":
                state = runtime.snapshot()
                self._send_json({"history": state["history"]})
                return
            if self.path == "/api/stats":
                state = runtime.snapshot()
                self._send_json({"stats": state["stats"]})
                return
            if self.path == "/healthz":
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
    handler = _make_handler(runtime, web_root)
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
