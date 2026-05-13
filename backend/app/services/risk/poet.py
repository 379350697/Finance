"""
POETCovEstimator: Principal Orthogonal complEment Thresholding (POET).

Decomposes covariance into:
    Sigma = B * Sigma_f * B' + Sigma_u

where B are the leading K principal components (factor loadings) and
Sigma_u is a sparse residual covariance estimated via adaptive thresholding.

Reference: Fan, Liao & Mincheva (2013), "Large Covariance Estimation by
Thresholding Principal Orthogonal Complements".
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


class POETCovEstimator:
    """POET covariance estimator.

    Parameters
    ----------
    k : int
        Number of principal components to retain as "factors".
    soft_threshold : bool
        If True, use soft-thresholding on residual covariance.
        If False, use hard-thresholding.
    """

    def __init__(self, k: int = 3, soft_threshold: bool = False):
        if k < 1:
            raise ValueError(f"k must be >= 1, got {k}")
        self.k = k
        self.soft_threshold = soft_threshold
        self._cov: np.ndarray | None = None
        self._loadings: np.ndarray | None = None
        self._residual_cov: np.ndarray | None = None

    @property
    def covariance(self) -> np.ndarray | None:
        return self._cov

    @property
    def loadings(self) -> np.ndarray | None:
        """Factor loadings, shape (n_assets, k)."""
        return self._loadings

    @property
    def residual_covariance(self) -> np.ndarray | None:
        """Threshold residual covariance, shape (n_assets, n_assets)."""
        return self._residual_cov

    def fit(self, returns: np.ndarray) -> POETCovEstimator:
        """Fit the POET estimator.

        Parameters
        ----------
        returns : np.ndarray, shape (n_periods, n_assets)

        Returns
        -------
        self
        """
        n, p = returns.shape

        if p < self.k * 2:
            # Too few assets for PCA — fall back to sample covariance
            logger.warning(
                "POET: p=%d < 2*k=%d, falling back to sample covariance",
                p, self.k * 2,
            )
            self._cov = np.cov(returns, rowvar=False)
            return self

        # 1. Sample covariance and eigendecomposition
        sample_cov = np.cov(returns, rowvar=False)
        eigenvalues, eigenvectors = np.linalg.eigh(sample_cov)

        # Sort descending
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]

        # 2. Low-rank factor component
        self._loadings = eigenvectors[:, :self.k]
        Lambda_k = np.diag(eigenvalues[:self.k])
        B_SigmaF_B = self._loadings @ Lambda_k @ self._loadings.T

        # 3. Residual covariance: sample_cov - B*Sigma_f*B'
        residual = sample_cov - B_SigmaF_B

        # 4. Adaptive thresholding on residuals
        # Threshold = C * sqrt(theta_ij / T)
        # where theta_ij = mean of (e_it * e_jt - sigma_u_ij)^2
        residuals_centered = returns - returns.mean(axis=0)
        common = residuals_centered @ self._loadings
        common = common @ self._loadings.T
        idiosyncratic = residuals_centered - common

        theta = np.zeros((p, p))
        for i in range(p):
            for j in range(p):
                cross = idiosyncratic[:, i] * idiosyncratic[:, j] - residual[i, j]
                theta[i, j] = np.mean(cross**2)

        threshold_mat = np.sqrt(theta / n)

        # Thresholding
        if self.soft_threshold:
            self._residual_cov = np.sign(residual) * np.maximum(
                np.abs(residual) - threshold_mat, 0
            )
        else:
            self._residual_cov = residual * (np.abs(residual) > threshold_mat)

        # 5. Reconstruct: factor + thresholded residual
        self._cov = B_SigmaF_B + self._residual_cov

        # Ensure symmetry and positive semi-definiteness
        self._cov = (self._cov + self._cov.T) / 2
        eig = np.linalg.eigh(self._cov)[0]
        if eig[0] < 1e-10:
            self._cov += np.eye(p) * max(0, -eig[0] + 1e-8)

        return self

    def get_covariance(self) -> np.ndarray:
        """Return the estimated covariance matrix."""
        if self._cov is None:
            raise RuntimeError("Must call fit() before get_covariance()")
        return self._cov
