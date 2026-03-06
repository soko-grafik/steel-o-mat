from __future__ import annotations

from statistics import median
from typing import Iterable


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5


def fuse_points(points: Iterable[tuple[float, float]], outlier_threshold_mm: float) -> tuple[float, float] | None:
    pts = list(points)
    if not pts:
        return None

    seed = (median([p[0] for p in pts]), median([p[1] for p in pts]))
    inliers = [p for p in pts if _distance(p, seed) <= outlier_threshold_mm]
    if not inliers:
        return seed
    return (
        float(sum(p[0] for p in inliers) / len(inliers)),
        float(sum(p[1] for p in inliers) / len(inliers)),
    )
