# Steel Dart Auto Scoring (3 USB Cameras)

This repository provides a prototype steel dart auto-scoring system based on three USB cameras.

## What is implemented
- Standard steel-dartboard scoring engine (single, double, triple, outer bull, double bull)
- 3-camera ingestion (OpenCV `VideoCapture`)
- Motion-based dart-tip detection (background subtraction)
- Per-camera homography projection from image pixels to board millimeters
- Multi-camera fusion with outlier rejection
- Web UI with PWA support (installable app)
- Game selection: `301`, `501`, `701`, `901`, `Cricket`, `Shanghai`
- Variation selection: `double_in`, `double_out`, `master_out`, `cut_throat`
- Multiplayer match management with max 4 players
- Leg/Set tracking with automatic player switching
- Cricket marks per player (`20..15` + `Bull`)
- Echte Checkout-Historie pro Dart und pro Turn
- Undo des letzten Darts
- Match-Statistik und Spieler-Statistik

## Project structure
- `src/darts/scoring.py`: board geometry and score calculation
- `src/darts/camera.py`: camera stream + tip detection + homography projection
- `src/darts/fusion.py`: combine detections from multiple cameras
- `src/darts/runtime.py`: game rules, multiplayer state, history/undo/statistics
- `src/darts/config.py`: load JSON configuration
- `src/darts/cli.py`: desktop CV loop with windows
- `src/darts/web.py`: HTTP server + REST API + static PWA hosting
- `web/`: PWA frontend files
- `tests/test_scoring.py`: unit tests for scoring/fusion/runtime/game rules

## Setup
1. Create a virtual environment.
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Copy sample config and set your real camera indices/homographies:

```powershell
Copy-Item config/cameras.example.json config/cameras.json
```

## Run web app (PWA)
```powershell
$env:PYTHONPATH='src'; python -m darts.web --config config/cameras.json --host 0.0.0.0 --port 8080
```

Then open `http://localhost:8080` in a browser.
Install the app via browser install prompt/menu.

Demo mode without cameras:
```powershell
$env:PYTHONPATH='src'; python -m darts.web --demo
```

## API summary
- `GET /api/state`: current throw + game + players + match status + history + stats
- `GET /api/game`: active game config
- `POST /api/game`: set game and variations
- `GET /api/match`: current multiplayer match snapshot
- `POST /api/match`: set players (1-4) and `legs_to_win_set`
- `GET /api/history`: dart- und turn-basierte Historie
- `GET /api/stats`: Match- und Spielerstatistik
- `POST /api/undo`: undo des letzten Darts
- `POST /api/simulate`: simulate a throw

## Calibration note
You must replace each camera's placeholder `homography` with a calibrated matrix that maps image points to board coordinates in millimeters (center at `(0, 0)`).
Without calibration, score positions are only approximate.
