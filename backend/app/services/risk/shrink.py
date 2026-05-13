"""
ShrinkCovEstimator: Ledoit-Wolf and OAS shrinkage covariance estimators.

Provides more robust covariance estimates than sample covariance by
shrinking towards a structured target (constant-correlation or identity).

Optionally uses sklearn.covariance if available; otherwise falls back
to a pure-numpy Ledoit-Wolf implementation.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

try:
    from sklearn.covariance import LedoitWolf, OAS

    _SKLEARN_AVAILABLE = True
except ImportError:  # pragma: no cover
    LedoitWolf = None
    OAS = None
    _SKLEARN_AVAILABLE = False
    logger.info("sklearn not installed; ShrinkCovEstimator uses numpy fallback.")


class ShrinkCovEstimator:
    """Shrinkage-based covariance estimation.

    Parameters
    ----------
    method : str
        "lw" for Ledoit-Wolf, "oas" for Oracle Approximating Shrinkage.
    """

    def __init__(self, method: str = "lw"):
        if method not in ("lw", "oas"):
            raise ValueError(f"method must be 'lw' or 'oas', got {method!r}")
        self.method = method
        self._cov: np.ndarray | None = None
        self._shrinkage: float = 0.0

    @property
    def covariance(self) -> np.ndarray | None:
        return self._cov

    @property
    def shrinkage(self) -> float:
        return self._shrinkage

    def fit(self, returns: np.ndarray) -> ShrinkCovEstimator:
        """Fit the shrinkage estimator on *returns*.

        Parameters
        ----------
        returns : np.ndarray, shape (n_periods, n_assets)
            Asset return series.

        Returns
        -------
        self
        """
        if returns.shape[0] < 3:
            self._cov = np.cov(returns, rowvar=False)
            return self

        if _SKLEARN_AVAILABLE and self.method == "lw":
            self._fit_sklearn_lw(returns)
        elif _SKLEARN_AVAILABLE and self.method == "oas":
            self._fit_sklearn_oas(returns)
        elif self.method == "lw":
            self._fit_numpy_lw(returns)
        else:
            # OAS without sklearn — fall back to LW + identity target
            self._fit_numpy_lw(returns)

        return self

    def _fit_sklearn_lw(self, returns: np.ndarray) -> None:
        lw = LedoitWolf().fit(returns)
        self._cov = lw.covariance_
        self._shrinkage = lw.shrinkage_ if hasattr(lw, "shrinkage_") else 0.0

    def _fit_sklearn_oas(self, returns: np.ndarray) -> None:
        oas = OAS().fit(returns)
        self._cov = oas.covariance_
        self._shrinkage = oas.shrinkage_ if hasattr(oas, "shrinkage_") else 0.0

    def _fit_numpy_lw(self, returns: np.ndarray) -> None:
        """Pure-numpy Ledoit-Wolf shrinkage estimator.

        Shrinks sample covariance towards a constant-correlation target.
        Reference: Ledoit & Wolf (2004), "Honey, I Shrunk the Sample
        Covariance Matrix".
        """
        n, p = returns.shape
        sample_cov = np.cov(returns, rowvar=False)

        # Constant-correlation target
        stds = np.sqrt(np.diag(sample_cov))
        correlations = sample_cov / np.outer(stds, stds)

        # Average correlation (off-diagonal)
        off_diag = correlations.copy()
        np.fill_diagonal(off_diag, 0.0)
        avg_corr = off_diag.sum() / (p * (p - 1)) if p > 1 else 0.0

        target = np.outer(stds, stds) * avg_corr
        np.fill_diagonal(target, stds**2)

        # Shrinkage intensity (Ledoit-Wolf formula)
        X = returns - returns.mean(axis=0)
        X2 = X**2

        # Compute pi_hat
        pi_mat = np.zeros((p, p))
        for i in range(n):
            cross = np.outer(X[i], X[i])
            pi_mat += (cross - sample_cov) ** 2
        pi_hat = pi_mat.sum() / n

        # Compute rho
        rho_off = 0.0
        for i in range(p):
            for j in range(p):
                if i == j:
                    continue
                theta_ij1 = np.mean(X2[:, i] * X[:, j])
                theta_ij2 = np.mean(X[:, i] * X2[:, j])
                rho_off += (theta_ij1 + theta_ij2) / 2

        gamma = np.sum((target - sample_cov) ** 2)

        # Shrinkage constant
        kappa = (pi_hat - rho_off) / max(gamma, 1e-12)
        delta = max(0.0, min(1.0, kappa / n))

        self._shrinkage = delta
        self._cov = delta * target + (1 - delta) * sample_cov

    def get_covariance(self) -> np.ndarray:
        """Return the estimated covariance matrix."""
        if self._cov is None:
            raise RuntimeError("Must call fit() before get_covariance()")
        return self._cov
