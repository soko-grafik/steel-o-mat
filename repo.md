# Repository Information: Steel Dart Auto Scoring

This project implements a prototype for an automatic steel dart scoring system utilizing three USB cameras. It features a Python-based backend for image processing and game logic, and a Progressive Web App (PWA) frontend for the user interface.

## Core Technologies
- **Backend**: Python 3, OpenCV (for camera ingestion and detection), NumPy (for mathematical operations and homography).
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla), PWA support.
- **Communication**: REST API (implemented in `src/darts/web.py`).

## Directory Structure
- [./src/darts/](./src/darts/): Core Python package containing the scoring engine, camera handling, and game runtime.
- [./web/](./web/): Frontend assets for the PWA.
- [./config/](./config/): Configuration files for camera settings and homography matrices.
- [./tests/](./tests/): Unit tests for backend logic.

## Key Backend Modules (`src/darts/`)
- [./src/darts/scoring.py](./src/darts/scoring.py): Handles board geometry and score calculations (Single, Double, Triple, Bull).
- [./src/darts/camera.py](./src/darts/camera.py): Manages camera streams, motion detection for dart tips, and image-to-millimeter projection.
- [./src/darts/fusion.py](./src/darts/fusion.py): Fuses detections from multiple cameras to increase accuracy and reject outliers.
- [./src/darts/runtime.py](./src/darts/runtime.py): Manages game states (301, 501, Cricket, etc.), player turns, history, and statistics.
- [./src/darts/web.py](./src/darts/web.py): Implements the Flask-like web server and API endpoints.
- [./src/darts/config.py](./src/darts/config.py): Utilities for loading and saving JSON configuration.

## Frontend (`web/`)
- [./web/index.html](./web/index.html): Main entry point for the web interface.
- [./web/app.js](./web/app.js): Main application logic for the frontend, handling API communication and UI updates.
- [./web/styles.css](./web/styles.css): Application styling.
- [./web/sw.js](./web/sw.js): Service worker for PWA offline support and installation.

## API Endpoints Summary
- `GET /api/state`: Retrieves the current match and game state.
- `POST /api/game`: Configures the active game type and variations.
- `POST /api/match`: Sets up players and match rules.
- `POST /api/undo`: Reverts the last recorded dart.
- `POST /api/simulate`: Allows manual score entry for testing or demo purposes.

## Configuration
Camera indices and homography matrices are defined in [./config/cameras.json](./config/cameras.json). A template is provided in [./config/cameras.example.json](./config/cameras.example.json).

## Testing
Unit tests are located in [./tests/test_scoring.py](./tests/test_scoring.py), covering scoring logic, fusion, and game rules.
