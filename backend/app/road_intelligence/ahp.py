"""
ahp.py
======
Analytic Hierarchy Process (AHP) weight calculation.

Implements the standard principal-eigenvector method:
  1. Build the pairwise comparison matrix (config.AHP_PAIRWISE_COMPARISON).
  2. Compute eigenvalues/eigenvectors.
  3. Take the eigenvector for the largest (principal) eigenvalue.
  4. Normalize it -> criterion weights (sum to 1.0).
  5. Compute Consistency Index (CI) and Consistency Ratio (CR).
  6. Flag (do not silently accept) matrices with CR > threshold.

Pure Python + numpy only — no pydantic/FastAPI dependency, so this is
independently unit-testable and reusable.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import config


class InconsistentMatrixError(ValueError):
    """Raised (or available to be raised) when a pairwise comparison
    matrix's Consistency Ratio exceeds the acceptable threshold."""


class InvalidMatrixError(ValueError):
    """Raised when the pairwise comparison matrix is structurally invalid
    (not square, not reciprocal, diagonal != 1, etc.)."""


@dataclass(frozen=True)
class AhpResult:
    criteria: list[str]
    weights: dict[str, float]
    lambda_max: float
    consistency_index: float
    consistency_ratio: float
    is_consistent: bool


def _validate_matrix(matrix: list[list[float]], n: int) -> None:
    if len(matrix) != n or any(len(row) != n for row in matrix):
        raise InvalidMatrixError(f"Pairwise comparison matrix must be {n}x{n}")

    for i in range(n):
        if abs(matrix[i][i] - 1.0) > 1e-9:
            raise InvalidMatrixError(f"Diagonal element [{i}][{i}] must be 1.0")

    for i in range(n):
        for j in range(n):
            if matrix[i][j] <= 0:
                raise InvalidMatrixError(f"Matrix entries must be positive (got [{i}][{j}]={matrix[i][j]})")
            if abs(matrix[i][j] * matrix[j][i] - 1.0) > 1e-6:
                raise InvalidMatrixError(
                    f"Matrix must be reciprocal: [{i}][{j}]={matrix[i][j]} and "
                    f"[{j}][{i}]={matrix[j][i]} are not reciprocals"
                )


def calculate_ahp_weights(
    criteria: list[str] | None = None,
    matrix: list[list[float]] | None = None,
) -> AhpResult:
    """Compute AHP criterion weights + consistency metrics.

    Defaults to config.AHP_CRITERIA / config.AHP_PAIRWISE_COMPARISON, but
    accepts overrides so the matrix can be swapped/tested without editing
    config.py (e.g. for admin-configurable weights in the future).
    """
    criteria = criteria if criteria is not None else config.AHP_CRITERIA
    matrix = matrix if matrix is not None else config.AHP_PAIRWISE_COMPARISON
    n = len(criteria)

    _validate_matrix(matrix, n)

    M = np.array(matrix, dtype=float)
    eigvals, eigvecs = np.linalg.eig(M)

    # Principal eigenvalue is the largest real eigenvalue for a valid
    # positive reciprocal matrix.
    real_eigvals = eigvals.real
    max_idx = int(np.argmax(real_eigvals))
    lambda_max = float(real_eigvals[max_idx])
    principal_vector = eigvecs[:, max_idx].real

    # Normalize (and ensure positive orientation).
    if principal_vector.sum() < 0:
        principal_vector = -principal_vector
    weights_arr = principal_vector / principal_vector.sum()
    # NOTE: intentionally NOT rounded here. Rounding each weight
    # independently (e.g. to 6dp) can make the set sum to 0.999999 or
    # 1.000001 instead of exactly 1.0, which then propagates into
    # priority-score contributions. Full precision is kept internally;
    # round only at presentation/serialization time if needed.
    weights = {c: float(w) for c, w in zip(criteria, weights_arr)}

    ci = (lambda_max - n) / (n - 1) if n > 1 else 0.0
    ri = config.AHP_RANDOM_INDEX.get(n, 1.49)  # 1.49 is the largest tabulated RI as a safe fallback
    cr = (ci / ri) if ri > 0 else 0.0
    is_consistent = cr <= config.AHP_CONSISTENCY_RATIO_THRESHOLD

    return AhpResult(
        criteria=list(criteria),
        weights=weights,
        lambda_max=round(lambda_max, 6),
        consistency_index=round(ci, 6),
        consistency_ratio=round(cr, 6),
        is_consistent=is_consistent,
    )


# Computed once at import time from the configured matrix. Importing
# modules (scoring.py) use this cached result rather than recomputing the
# eigen-decomposition on every request, since the matrix is static
# configuration, not per-request input.
DEFAULT_AHP_RESULT: AhpResult = calculate_ahp_weights()

if not DEFAULT_AHP_RESULT.is_consistent:
    # Fail loudly at import time rather than silently serving an
    # inconsistent priority model. If you edit config.AHP_PAIRWISE_COMPARISON
    # and this fires, revise the matrix until CR <= 0.10.
    raise InconsistentMatrixError(
        f"config.AHP_PAIRWISE_COMPARISON is inconsistent: "
        f"CR={DEFAULT_AHP_RESULT.consistency_ratio} > "
        f"{config.AHP_CONSISTENCY_RATIO_THRESHOLD}"
    )
