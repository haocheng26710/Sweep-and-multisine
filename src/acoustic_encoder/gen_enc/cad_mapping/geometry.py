from fractions import Fraction


def signed_area(points):
    values = [(Fraction(str(x)), Fraction(str(y))) for x, y in points]
    return sum(values[i][0] * values[(i + 1) % len(values)][1] - values[(i + 1) % len(values)][0] * values[i][1] for i in range(len(values))) / 2


def clip_polygon(points, normal, offset):
    n0, n1, off = Fraction(str(normal[0])), Fraction(str(normal[1])), Fraction(str(offset))
    source = [(Fraction(str(x)), Fraction(str(y))) for x, y in points]
    result = []
    for index, current in enumerate(source):
        previous = source[index - 1]
        cv = n0 * current[0] + n1 * current[1] - off
        pv = n0 * previous[0] + n1 * previous[1] - off
        if cv <= 0:
            if pv > 0:
                ratio = pv / (pv - cv)
                result.append((previous[0] + ratio * (current[0] - previous[0]), previous[1] + ratio * (current[1] - previous[1])))
            result.append(current)
        elif pv <= 0:
            ratio = pv / (pv - cv)
            result.append((previous[0] + ratio * (current[0] - previous[0]), previous[1] + ratio * (current[1] - previous[1])))
    return result
