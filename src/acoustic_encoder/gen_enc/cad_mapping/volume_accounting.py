from fractions import Fraction


def box_union_volume(boxes):
    if not boxes:
        return 0.0
    axes = [[sorted({Fraction(str(box[axis][end])) for box in boxes for end in (0, 1)}) for axis in range(3)]][0]
    total = Fraction(0)
    for xi in range(len(axes[0]) - 1):
        for yi in range(len(axes[1]) - 1):
            for zi in range(len(axes[2]) - 1):
                lows = (axes[0][xi], axes[1][yi], axes[2][zi])
                highs = (axes[0][xi + 1], axes[1][yi + 1], axes[2][zi + 1])
                mids = tuple((a + b) / 2 for a, b in zip(lows, highs))
                if any(all(Fraction(str(box[a][0])) < mids[a] < Fraction(str(box[a][1])) for a in range(3)) for box in boxes):
                    total += (highs[0] - lows[0]) * (highs[1] - lows[1]) * (highs[2] - lows[2])
    return float(total)
