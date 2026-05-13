"""
StructuredCovEstimator: Factor-model-based covariance estimation.

Decomposes asset returns as:
    r = B * f + epsilon

where B are factor loadings (betas) and epsilon is idiosyncratic noise.

Covariance: Sigma = B @ Sigma_f @ B' + diag(sigma_epsilon^2)
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


class StructuredCovEstimator:
    """Factor-model structured covariance estimator.

    Parameters
    ----------
    n_factors : int
        Number of factors to use.  The first *n_factors* columns of the
        returns matrix are treated as factors; the remaining columns are
        assets whose covariance is estimated.
    """

    def __init__(self, n_factors: int = 5):
        if n_factors < 1:
            raise ValueError(f"n_factors must be >= 1, got {n_factors}")
        self.n_factors = n_factors
        self._cov: np.ndarray | None = None
        self._loadings: np.ndarray | None = None
        self._factor_cov: np.ndarray | None = None
        self._idiosyncratic_var: np.ndarray | None = None

    @property
    def covariance(self) -> np.ndarray | None:
        return self._cov

    @property
    def loadings(self) -> np.ndarray | None:
        """Factor loadings (betas), shape (n_assets, n_factors)."""
        return self._loadings

    @property
    def factor_covariance(self) -> np.ndarray | None:
        """Covariance of factors, shape (n_factors, n_factors)."""
        return self._factor_cov

    @property
    def idiosyncratic_variance(self) -> np.ndarray | None:
        """Idiosyncratic variances, shape (n_assets,)."""
        return self._idiosyncratic_var

    def fit(self, returns: np.ndarray) -> StructuredCovEstimator:
        """Fit the structured covariance estimator.

        Parameters
        ----------
        returns : np.ndarray, shape (n_periods, n_assets)
            The first *n_factors* columns are treated as factor returns;
            remaining columns are asset returns.

        Returns
        -------
        self
        """
        n_periods, n_cols = returns.shape
        if n_cols <= self.n_factors:
            raise ValueError(
                f"Need more columns ({n_cols}) than factors ({self.n_factors})"
            )

        # Split into factor returns (F) and asset returns (R)
        F = returns[:, :self.n_factors]          # (T, k)
        R = returns[:, self.n_factors:]           # (T, p)

        p_assets = R.shape[1]

        # Factor covariance
        self._factor_cov = np.cov(F, rowvar=False)  # (k, k)

        # Estimate loadings via OLS: R_t = B @ F_t + epsilon_t
        # B = (F'F)^{-1} F'R
        try:
            FtF_inv = np.linalg.inv(F.T @ F)
        except np.linalg.LinAlgError:
            FtF_inv = np.linalg.pinv(F.T @ F)

        self._loadings = FtF_inv @ F.T @ R          # (k, p)
        self._loadings = self._loadings.T            # (p, k)

        # Idiosyncratic variance: diag of residual covariance
        residuals = R - F @ self._loadings.T         # (T, p)
        self._idiosyncratic_var = np.var(residuals, axis=0, ddof=1)  # (p,)

        # Full covariance
        systematic = (
            self._loadings @ self._factor_cov @ self._loadings.T
        )  # (p, p)
        idiosyncratic = np.diag(self._idiosyncratic_var)

        self._cov = systematic + idiosyncratic

        return self

    def get_covariance(self) -> np.ndarray:
        """Return the full estimated covariance matrix (n_assets, n_assets)."""
        if self._cov is None:
            raise RuntimeError("Must call fit() before get_covariance()")
        return self._cov

    def get_systematic_covariance(self) -> np.ndarray:
        """Return only the systematic component B @ Sigma_f @ B'."""
        if self._loadings is None or self._factor_cov is None:
            raise RuntimeError("Must call fit() first")
        return self._loadings @ self._factor_cov @ self._loadings.T
