"""Five level frequency encoding.
Numerical functions and frozen parameters used in Draft 18.
Run this script to calculate the bounded example from its supplied datasets.
Additional original numerical functions are available for explicit use.
Requirements: Python 3.11+ and NumPy; SciPy/scikit-learn where imported.
"""
from __future__ import annotations
from pathlib import Path
import json
import csv
import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "datasets" / "08_five_level_frequency_encoding"


# Gen enc 24 print comp analysis

SPAN = 201.0

Q = 12.0

def calibration_marker(values, target=950.0):
    f = np.arange(target - 130, target + 130.1, 2.0)
    db = np.mean(20 * np.log10(np.maximum(np.abs(values), 1e-30)), axis=0)
    best = (-float('inf'), float('nan'))
    for center in np.arange(target - 30, target + 30.01, 2.0):
        mask = np.abs(f - center) <= SPAN / 2
        ff = f[mask]
        yy = db[mask]
        x = (ff - center) / (SPAN / 2)
        lorentz = 1 / (1 + (2 * Q * (ff - center) / center) ** 2)
        amp = float(np.linalg.lstsq(np.column_stack((np.ones_like(x), x, -lorentz)), yy, rcond=None)[0][-1])
        if amp > best[0]:
            best = (amp, center)
    return {'tracked_hz': best[1], 'fitted_depth_db': max(0.0, best[0]), 'at_search_boundary': bool(best[1] in (target - 30, target + 30))}


# Gen enc 26 print conv b analysis

def read_case(root: Path, label: str, size: int, target: float):
    f = np.arange(target - 130, target + 130.1, 2.0)
    rows = []
    for source in range(4):
        path = root / f'{label}_size{size}_src{source}.txt'
        lines = [x.strip() for x in path.read_text(encoding='utf-8').splitlines() if x.strip() and (not x.startswith('%'))]
        if len(lines) != 1:
            raise RuntimeError(f'BAD_EXPORT:{path.name}')
        values = np.asarray([complex(x.replace('i', 'j')) for x in lines[0].split()[3:]])
        if len(values) != len(f) or not np.isfinite(values).all():
            raise RuntimeError(f'BAD_VALUES:{path.name}')
        rows.append(values)
    return np.stack(rows)

def convergence_marker(values, target):
    f = np.arange(target - 130, target + 130.1, 2.0)
    db = np.mean(20 * np.log10(np.maximum(np.abs(values), 1e-30)), axis=0)
    best = (-float('inf'), float('nan'))
    for center in np.arange(target - 30, target + 30.01, 2.0):
        mask = np.abs(f - center) <= 201 / 2
        ff = f[mask]
        yy = db[mask]
        x = (ff - center) / (201 / 2)
        lorentz = 1 / (1 + (2 * 12 * (ff - center) / center) ** 2)
        amp = float(np.linalg.lstsq(np.column_stack((np.ones_like(x), x, -lorentz)), yy, rcond=None)[0][-1])
        if amp > best[0]:
            best = (amp, center)
    return {'tracked_hz': best[1], 'fitted_depth_db': max(0.0, best[0]), 'at_search_boundary': bool(best[1] in (target - 30, target + 30))}

def rel(a, b):
    return float(np.linalg.norm(a - b) / np.linalg.norm(a))

def metrics(a, b):
    gain = np.vdot(b, a) / np.vdot(b, b)
    return {'complex_relative_l2': rel(a, b), 'magnitude_relative_l2': float(np.linalg.norm(np.abs(a) - np.abs(b)) / np.linalg.norm(np.abs(a))), 'gain_aligned_complex_relative_l2': float(np.linalg.norm(a - gain * b) / np.linalg.norm(a)), 'best_fit_gain_magnitude': float(abs(gain)), 'best_fit_gain_phase_deg': float(np.angle(gain, deg=True))}

def read_source(root: Path, label: str, size: int, source: int, target: float):
    f = np.arange(target - 130, target + 130.1, 2.0)
    path = root / f'{label}_size{size}_src{source}.txt'
    lines = [x.strip() for x in path.read_text(encoding='utf-8').splitlines() if x.strip() and (not x.startswith('%'))]
    if len(lines) != 1:
        raise RuntimeError(f'BAD_EXPORT:{path.name}')
    values = np.asarray([complex(x.replace('i', 'j')) for x in lines[0].split()[3:]])
    if len(values) != len(f) or not np.isfinite(values).all():
        raise RuntimeError(f'BAD_VALUES:{path.name}')
    return values


# Gen enc 28 print blind c analysis

def mapping_marker(v, target):
    f = np.arange(target - 130, target + 130.1, 2.0)
    db = np.mean(20 * np.log10(np.maximum(np.abs(v), 1e-30)), axis=0)
    best = (-1e+99, np.nan)
    for c in np.arange(target - 30, target + 30.01, 2.0):
        q = np.abs(f - c) <= 201 / 2
        ff = f[q]
        yy = db[q]
        x = (ff - c) / (201 / 2)
        lor = 1 / (1 + (24 * (ff - c) / c) ** 2)
        amp = float(np.linalg.lstsq(np.column_stack((np.ones_like(x), x, -lor)), yy, rcond=None)[0][-1])
        if amp > best[0]:
            best = (amp, c)
    return {'tracked_hz': best[1], 'fitted_depth_db': max(0.0, best[0]), 'at_search_boundary': bool(best[1] in (target - 30, target + 30))}


# Gen enc 31 print tol a analysis

def tolerance_marker(v, target):
    f = np.arange(target - 130, target + 130.1, 2.0)
    db = np.mean(20 * np.log10(np.maximum(abs(v), 1e-30)), axis=0)
    best = (-1e+99, np.nan)
    for c in np.arange(target - 60, target + 60.1, 2.0):
        q = abs(f - c) <= 100.5
        ff = f[q]
        x = (ff - c) / 100.5
        lor = 1 / (1 + (24 * (ff - c) / c) ** 2)
        amp = float(np.linalg.lstsq(np.column_stack((np.ones(q.sum()), x, -lor)), db[q], rcond=None)[0][-1])
        best = (amp, c) if amp > best[0] else best
    return {'tracked_hz': best[1], 'fitted_depth_db': max(0.0, best[0]), 'boundary': bool(best[1] in (target - 60, target + 60))}


def paper_example():
    """Recompute the five frozen nominal frequency markers and bounded intervals.

    Public levels 0.03/0.05/0.07 use the endpoint stage; the archived blind levels
    0.04/0.06 use the mapping stage. The 9-mm neck remains fixed. Calibration,
    convergence, mapping and tolerance marker functions retain their distinct
    original search windows. No simulation or new parameter selection runs.
    """
    nominal = []
    intervals = []
    for a in (3, 4, 5, 6, 7):
        alpha = a / 100.0
        target = {3: 1150.0, 4: 1050.0, 5: 950.0, 6: 850.0, 7: 750.0}[a]
        folder, prefix = ('five_level_mapping', 'BLIND') if a in (4, 6) else ('endpoint_mesh_check', 'FC')
        pressure = read_case(DATA_DIR / folder / 'complex_spectra', f'{prefix}_L0900_A{a:02d}', 2, target)
        result = (mapping_marker if a in (4, 6) else convergence_marker)(pressure, target)
        nominal.append({'alpha': alpha, 'target_hz': target, **result})
        bounds = []
        for corner in ('LOW', 'HIGH'):
            pressure = read_case(DATA_DIR / 'bounded_tolerance/complex_spectra', f'CORNER_{corner}_A{a:02d}', 2, target)
            bounds.append(tolerance_marker(pressure, target)['tracked_hz'])
        intervals.append(bounds)
    target = np.asarray([row['target_hz'] for row in nominal])
    tracked = np.asarray([row['tracked_hz'] for row in nominal])
    slope, intercept = np.polyfit(target, tracked, 1)
    r2 = 1 - np.sum((tracked - (slope * target + intercept)) ** 2) / np.sum((tracked - tracked.mean()) ** 2)
    gaps = [intervals[i][0] - intervals[i + 1][1] for i in range(4)]
    return {'nominal': nominal, 'maximum_error_hz': float(np.max(abs(tracked - target))),
            'rmse_hz': float(np.sqrt(np.mean((tracked - target) ** 2))), 'slope': float(slope), 'intercept_hz': float(intercept),
            'r_squared': float(r2), 'tolerance_intervals_hz': intervals, 'adjacent_gaps_hz': gaps}

if __name__ == '__main__':
    print(json.dumps(paper_example(), indent=2))

