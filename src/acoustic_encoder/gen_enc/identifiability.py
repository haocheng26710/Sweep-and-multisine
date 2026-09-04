"""Algebraic GEN-ENC E1 identities; no performance evaluation."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def observable_operator(a: ArrayLike, c: ArrayLike, b: ArrayLike) -> NDArray[np.complex128]:
    """Return the observable product H=A C B."""

    return np.asarray(a, dtype=np.complex128) @ np.asarray(c, dtype=np.complex128) @ np.asarray(
        b, dtype=np.complex128
    )


def gauge_transform(
    a: ArrayLike,
    c: ArrayLike,
    b: ArrayLike,
    q: ArrayLike,
    r: ArrayLike,
) -> tuple[NDArray[np.complex128], NDArray[np.complex128], NDArray[np.complex128]]:
    """Apply A'=A Q^-1, C'=Q C R^-1, B'=R B.

    Q and R must be square and nonsingular.  The returned factors have the
    same observable product as the inputs, up to floating-point roundoff.
    """

    aa = np.asarray(a, dtype=np.complex128)
    cc = np.asarray(c, dtype=np.complex128)
    bb = np.asarray(b, dtype=np.complex128)
    qq = np.asarray(q, dtype=np.complex128)
    rr = np.asarray(r, dtype=np.complex128)
    q_inv = np.linalg.inv(qq)
    r_inv = np.linalg.inv(rr)
    return aa @ q_inv, qq @ cc @ r_inv, rr @ bb


def shared_differential_rank_ceiling(state_count: int) -> int:
    """Return rank(P_diff)=K-1 for K states."""

    if state_count < 1:
        raise ValueError("state_count must be positive")
    return state_count - 1
