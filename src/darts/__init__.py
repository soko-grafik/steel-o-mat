import os

# Suppress noisy OpenCV logs and problematic backends
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"
os.environ["OPENCV_VIDEOIO_PRIORITY_OBSENSOR"] = "0"
os.environ["OPENCV_VIDEOIO_PRIORITY_FFMPEG"] = "0"

from .config import SystemConfig, load_config
from .fusion import fuse_points
from .runtime import RuntimeState, ScoreState
from .scoring import ScoreResult, score_point

__all__ = [
    "SystemConfig",
    "load_config",
    "fuse_points",
    "RuntimeState",
    "ScoreState",
    "ScoreResult",
    "score_point",
]
