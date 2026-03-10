# Repository Information: Steel Dart Auto Scoring

This project implements a prototype for an automatic steel dart scoring system utilizing three USB cameras. It features a Python-based backend for image processing and game logic, and a Progressive Web App (PWA) frontend for the user interface.

## Core Technologies
- **Backend**: Python 3, OpenCV (for camera ingestion and detection), NumPy (for mathematical operations and homography), SQLite (for data persistence).
- **Frontend**: React (Vite), eigenes CSS-Design (PWA-fähig) für mobile und Desktop-Nutzung.
- **Communication**: REST API (implemented in `src/darts/web.py`) for frontend-backend interaction.

## Directory Structure
- [./src/darts/](./src/darts/): Core Python package containing the scoring engine, camera handling, and game runtime.
- [./web/](./web/): React frontend (source + build output for PWA hosting).
- [./config/](./config/): Configuration files for camera settings, players, and the SQLite database.
- [./tests/](./tests/): Unit tests for backend logic, scoring, and game rules.
- [./demo_assets/](./demo_assets/): Assets for demo mode.

## Key Backend Modules (`src/darts/`)
- [./src/darts/scoring.py](./src/darts/scoring.py): Handles board geometry and score calculations (Single, Double, Triple, Bull).
- [./src/darts/camera.py](./src/darts/camera.py): Manages camera streams, motion detection for dart tips, and image-to-millimeter projection.
- [./src/darts/fusion.py](./src/darts/fusion.py): Fuses detections from multiple cameras to increase accuracy and reject outliers.
- [./src/darts/runtime.py](./src/darts/runtime.py): Manages game states (301, 501, Cricket, etc.), player turns, history, and statistics.
- [./src/darts/web.py](./src/darts/web.py): Implements the Flask-like web server and API endpoints.
- [./src/darts/db.py](./src/darts/db.py): Manages SQLite database for persisting settings, players, matches, and individual throws.
- [./src/darts/calibration_auto.py](./src/darts/calibration_auto.py): Automated calibration point detection using color-based segmentation (Red/Green rings).
- [./src/darts/cli.py](./src/darts/cli.py): Desktop-based command-line interface with OpenCV window previews for debugging and manual use.
- [./src/darts/config.py](./src/darts/config.py): Utilities for loading and saving JSON configuration files.

## Frontend (`web/`)
- [./web/src/main.jsx](./web/src/main.jsx): React bootstrap with HeroUI provider and service worker registration.
- [./web/src/App.jsx](./web/src/App.jsx): Main frontend dashboard and API integration.
- [./web/src/styles.css](./web/src/styles.css): Tailwind CSS entry for the React UI.
- [./web/sw.js](./web/sw.js): Service worker enabling PWA features like offline support and local caching.

## API Endpoints Summary
- `GET /api/state`: Retrieves the comprehensive current match and game state.
- `POST /api/game`: Configures the active game type (e.g., 501, Cricket) and variations.
- `POST /api/match`: Sets up players, legs per set, and other match rules.
- `POST /api/undo`: Reverts the last recorded dart throw.
- `POST /api/simulate`: Allows manual score entry or simulation for testing and demo purposes.

## Configuration & Data
- **Camera Settings**: Defined in [./config/cameras.json](./config/cameras.json) (template: [./config/cameras.example.json](./config/cameras.example.json)).
- **Database**: The system uses `config/darts.db` for long-term storage of game history and player profiles.
- **Players**: Global players can also be configured in [./config/players.json](./config/players.json).

## Testing & Quality
- **Unit Tests**: Located in [./tests/test_scoring.py](./tests/test_scoring.py), validating core scoring logic, multi-camera fusion, and game rules.
- **Diagnostics**: The codebase includes extensive logging and debugging tools in `cli.py` and `web.py`.
