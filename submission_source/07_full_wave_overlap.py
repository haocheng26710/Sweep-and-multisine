"""Full wave overlap.
Numerical functions and frozen parameters used in Draft 18.
Run this script to calculate the bounded example from its supplied datasets.
Additional original numerical functions are available for explicit use.
Requirements: Python 3.11+ and NumPy; SciPy/scikit-learn where imported.
"""
from __future__ import annotations
from pathlib import Path
import json
import csv
from numpy.typing import NDArray
import math
import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "datasets" / "07_full_wave_overlap"


# E2 authority

PORT_ANGLES_DEGREES = (0.0, 90.0, 180.0, 270.0)

class E2AuthorityError(ValueError):
    """Fail-closed authority-rule violation."""

def directional_port_weights(angle_degrees: float, angle_offset_degrees: float) -> NDArray[np.float64]:
    """Return the L2-normalized, common-zero-phase angle-to-port vector."""
    theta = float(angle_degrees)
    offset = float(angle_offset_degrees)
    if not math.isfinite(theta) or not math.isfinite(offset):
        raise E2AuthorityError('FINITE_ANGLE_AND_OFFSET_REQUIRED')
    theta_effective = (theta + offset) % 360.0
    radians = np.deg2rad(theta_effective - np.asarray(PORT_ANGLES_DEGREES, dtype=np.float64))
    raw = np.maximum(0.0, np.cos(radians))
    raw[np.abs(raw) < 1e-15] = 0.0
    norm = float(np.linalg.norm(raw, ord=2))
    if not math.isfinite(norm) or norm <= 0.0:
        raise E2AuthorityError('ANGLE_TO_PORT_VECTOR_UNAVAILABLE')
    weights = raw / norm
    weights[np.abs(weights) < 1e-15] = 0.0
    return weights


# Gen enc 5 obsa readout bottleneck diagnostic

readout_PAIRS = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))

def state_signature(response: np.ndarray, *, center: bool) -> np.ndarray:
    x = np.asarray(response, dtype=np.complex128).reshape(4, -1)
    contrast_fraction = float(np.linalg.norm(x - np.mean(x, axis=0, keepdims=True)) / np.linalg.norm(x))
    if center:
        x = x - np.mean(x, axis=0, keepdims=True)
    norm = float(np.linalg.norm(x))
    if norm <= 0 or not math.isfinite(norm):
        raise RuntimeError('ZERO_OR_NONFINITE_LAYER_RESPONSE')
    x = x / norm
    gram = x @ x.conj().T
    gram = 0.5 * (gram + gram.conj().T)
    distances = np.asarray([np.linalg.norm(x[left] - x[right]) for left, right in readout_PAIRS], dtype=float)
    singular = np.linalg.svd(np.concatenate((x.real, x.imag), axis=1), compute_uv=False)
    singular = singular / singular.sum()
    return np.concatenate((gram.real.reshape(-1), gram.imag.reshape(-1), distances, singular, np.asarray([contrast_fraction])))


# Gen enc 8 comsol fullwave pilot analysis

ORDER = ('HAND_01', 'NEAR_01', 'RANDOM_01', 'PHYSICS_01')

pilot_PAIRS = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))

def pilot_expanded_response(port_transfer: np.ndarray) -> np.ndarray:
    """Rebuild the frozen four-state x four-port response by linearity."""
    result = np.empty((4, 4, port_transfer.shape[1]), dtype=np.complex128)
    for state_index, angle in enumerate((0.0, 90.0, 180.0, 270.0)):
        weights = directional_port_weights(angle, 0.0)
        result[state_index] = weights[:, None] * port_transfer
    return result

def distances(signatures: np.ndarray) -> dict[str, object]:
    rows = []
    for left, right in pilot_PAIRS:
        rows.append({'representatives': [ORDER[left], ORDER[right]], 'distance': float(np.linalg.norm(signatures[left] - signatures[right]))})
    values = np.asarray([row['distance'] for row in rows])
    return {'minimum': float(values.min()), 'mean': float(values.mean()), 'pairwise': rows}


# Gen enc 9 loss 3d bridge analysis

def complex_array(value: object) -> np.ndarray:
    data = np.asarray(value, dtype=float)
    if data.shape[-1] != 2:
        raise RuntimeError('COMPLEX_PAIR_AXIS_REQUIRED')
    return data[..., 0] + 1j * data[..., 1]

def lossy_expanded_response(port_transfer: np.ndarray) -> np.ndarray:
    result = np.empty((4, 4, port_transfer.shape[1]), dtype=np.complex128)
    for state_index, angle in enumerate((0.0, 90.0, 180.0, 270.0)):
        result[state_index] = directional_port_weights(angle, 0.0)[:, None] * port_transfer
    return result

def signature(port_transfer: np.ndarray) -> np.ndarray:
    return state_signature(lossy_expanded_response(port_transfer), center=False)

def pair_distance(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.linalg.norm(signature(left) - signature(right)))

def relative_l2(reference: np.ndarray, alternative: np.ndarray) -> float:
    return float(np.linalg.norm(alternative - reference) / np.linalg.norm(reference))


def paper_example():
    """Calculate HAND/NEAR overlap from the archived converged lossy 3-D responses.

    JSON complex values are [real, imaginary] pressure pairs. The chosen converged
    grids are the archived HAND size-1 and NEAR size-1 grids, with no new solve.
    The same file retains the 2-D pilot and preceding 3-D mesh comparisons.
    """
    raw = json.loads((DATA_DIR / 'complex_responses.json').read_text(encoding='utf-8'))
    hand = complex_array(raw['lossy3d_final_refinement_raw']['responses']['HAND_01']['values'])
    near = complex_array(raw['near_lossy3d_size1_raw']['responses'])
    return {'lossy_3d_hand_near_distance': pair_distance(hand, near),
            'hand_shape': list(hand.shape), 'near_shape': list(near.shape),
            'frequencies_hz': raw['lossy3d_final_refinement_raw']['frequencies_hz']}

if __name__ == '__main__':
    print(json.dumps(paper_example(), indent=2))

