import math

from .geometry import signed_area


def polygon_clearance(points):
    if signed_area(points) == 0:
        raise ValueError("DEGENERATE_BOUNDARY_FACE")
    distances = []
    for left, right in zip(points, points[1:]):
        distances.append(math.dist(left, right))
    return min(distances) if distances else None
