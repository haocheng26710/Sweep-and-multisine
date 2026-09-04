SECTORS = (("000", 1.0, 0.0), ("090", 0.0, 1.0), ("180", -1.0, 0.0), ("270", 0.0, -1.0))


def owner(x, y, half_extent):
    if -half_extent <= x < half_extent and -half_extent <= y < half_extent:
        return "CENTRAL"
    scores = [(x * dx + y * dy, sector) for sector, dx, dy in SECTORS]
    best = max(score for score, _ in scores)
    return min(sector for score, sector in scores if score == best)


def positive_crossing(points, half_extent):
    return len({owner(float(x), float(y), half_extent) for x, y in points}) > 1
