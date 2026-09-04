import math


def bisect_linear(target, lower, upper, intercept, slope):
    def value(x):
        return intercept + slope * x
    lo_value, hi_value = value(lower), value(upper)
    if not (lo_value <= target <= hi_value) or slope <= 0.0:
        raise ValueError("ROOT_NOT_BRACKETED")
    if target == lo_value:
        return lower
    if target == hi_value:
        return upper
    lo, hi = lower, upper
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if value(mid) < target:
            lo = mid
        else:
            hi = mid
    root = lo if abs(value(lo) - target) <= abs(value(hi) - target) else hi
    if not math.isfinite(root):
        raise ValueError("NONFINITE")
    return root


def q270_target(x, y, z, total=3.014899604922098e-5):
    q = [x, y, z, -(x + y + z) / 3.0]
    weights = [math.exp(v) for v in q]
    return 0.60 * total * weights[3] / sum(weights)
