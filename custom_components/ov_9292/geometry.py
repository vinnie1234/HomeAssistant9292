"""Route geometry from 9292 ("LINESTRING (lon lat, ...)") as [[lat, lon], ...] for the map."""

from __future__ import annotations

import math
import re

_NUMBER_PAIR = re.compile(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)")


def parse_linestring(wkt: str | None) -> list[list[float]]:
    """'LINESTRING (5.52 52.02, 5.53 52.03)' -> [[52.02, 5.52], [52.03, 5.53]] (WKT is lon lat)."""
    return [[float(lat), float(lon)] for lon, lat in _NUMBER_PAIR.findall(wkt or "")]


def simplify_path(points: list[list[float]], tolerance: float = 0.0001) -> list[list[float]]:
    """Ramer-Douglas-Peucker; ~11 m tolerance keeps the shape but cuts most of the points."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        (ax, ay), (bx, by) = points[first], points[last]
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        farthest, farthest_distance = -1, 0.0
        for i in range(first + 1, last):
            px, py = points[i]
            t = 0.0 if length_sq == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
            d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
            if d > farthest_distance:
                farthest, farthest_distance = i, d
        if farthest_distance > tolerance:
            keep[farthest] = True
            stack += [(first, farthest), (farthest, last)]
    return [point for point, kept in zip(points, keep) if kept]
