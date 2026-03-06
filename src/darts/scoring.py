from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, hypot

SECTOR_ORDER_CLOCKWISE_FROM_TOP = [
    20, 1, 18, 4, 13, 6, 10, 15, 2, 17,
    3, 19, 7, 16, 8, 11, 14, 9, 12, 5,
]

R_DB = 6.35
R_OB = 15.9
R_T_INNER = 99.0
R_T_OUTER = 107.0
R_D_INNER = 162.0
R_D_OUTER = 170.0


@dataclass(slots=True)
class ScoreResult:
    points: int
    bed: str
    number: int | None
    radius_mm: float
    angle_deg: float


def _sector_number(x_mm: float, y_mm: float) -> int:
    angle_deg = degrees(atan2(y_mm, x_mm))
    sector_index = int(((90.0 - angle_deg) % 360.0) // 18.0)
    return SECTOR_ORDER_CLOCKWISE_FROM_TOP[sector_index]


def score_point(x_mm: float, y_mm: float) -> ScoreResult:
    radius = hypot(x_mm, y_mm)
    angle_deg = degrees(atan2(y_mm, x_mm))

    if radius > R_D_OUTER:
        return ScoreResult(points=0, bed="MISS", number=None, radius_mm=radius, angle_deg=angle_deg)
    if radius <= R_DB:
        return ScoreResult(points=50, bed="DB", number=25, radius_mm=radius, angle_deg=angle_deg)
    if radius <= R_OB:
        return ScoreResult(points=25, bed="OB", number=25, radius_mm=radius, angle_deg=angle_deg)

    number = _sector_number(x_mm, y_mm)

    if R_D_INNER <= radius <= R_D_OUTER:
        return ScoreResult(points=number * 2, bed="D", number=number, radius_mm=radius, angle_deg=angle_deg)
    if R_T_INNER <= radius <= R_T_OUTER:
        return ScoreResult(points=number * 3, bed="T", number=number, radius_mm=radius, angle_deg=angle_deg)
    return ScoreResult(points=number, bed="S", number=number, radius_mm=radius, angle_deg=angle_deg)
