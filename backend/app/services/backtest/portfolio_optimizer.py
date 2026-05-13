"""PortfolioOptimizer: weight optimization for backtest position sizing."""

from __future__ import annotations

import numpy as np
import pandas as pd

try:
    import cvxpy as cp
    _CVXPY_AVAILABLE = True
except ImportError:
    cp = None
    _CVXPY_AVAILABLE = False

try:
    from scipy.optimize import minimize
    _SCIPY_OPT_AVAILABLE = True
except ImportError:
    minimize = None
    _SCIPY_OPT_AVAILABLE = False


class PortfolioOptimizer:
    """Optimizes portfolio weights for backtest position sizing.

    Methods:
        - equal_weight: uniform allocation
        - risk_parity: equal risk contribution (uses scipy)
        - mean_variance: max expected return - lambda * variance
        - max_sharpe: maximize Sharpe ratio
        - min_variance: minimize portfolio variance

    Constraints (optional):
        - max_weight_per_stock: e.g. 0.05 = max 5%
        - max_turnover: max weight change from previous weights
    """

    def __init__(self, method: str = "equal_weight",
                 constraints: dict | None = None,
                 cov_estimator: object = None):
        self.method = method
        self.constraints = constraints or {}
        self._prev_weights: np.ndarray | None = None
        self._cov_estimator = cov_estimator

    def optimize(self, returns: pd.DataFrame,  # (n_dates, n_assets)
                 scores: pd.DataFrame | None = None,  # model scores for mean-variance
                 ) -> np.ndarray:
        """Compute optimal weights. Returns array of shape (n_assets,)."""
        n = returns.shape[1]
        if n == 0:
            return np.array([])
        if n == 1:
            return np.ones(1)

        if self.method == "equal_weight":
            return self._equal_weight(returns)
        elif self.method == "risk_parity":
            return self._risk_parity(returns)
        elif self.method == "mean_variance":
            return self._mean_variance(returns, scores)
        elif self.method == "max_sharpe":
            return self._max_sharpe(returns, scores)
        elif self.method == "min_variance":
            return self._min_variance(returns)
        else:
            raise ValueError(f"Unknown method: {self.method}")

    def _equal_weight(self, returns: pd.DataFrame) -> np.ndarray:
        n = returns.shape[1]
        return np.ones(n) / n

    def _cov(self, returns: pd.DataFrame) -> np.ndarray:
        """Covariance matrix (via estimator if set, else sample cov)."""
        values = returns.values
        if self._cov_estimator is not None:
            try:
                self._cov_estimator.fit(values)
                return self._cov_estimator.get_covariance()
            except Exception:
                pass  # fall back to sample covariance
        cov = np.cov(values, rowvar=False)
        return cov + np.eye(len(cov)) * 1e-8

    def _risk_parity(self, returns: pd.DataFrame) -> np.ndarray:
        """Risk parity via scipy.optimize.

        Minimizes sum_i sum_j (w_i * (Cov w)_i - w_j * (Cov w)_j)^2
        subject to sum(w) = 1, w >= 0.
        """
        cov = self._cov(returns)
        n = len(cov)

        def risk_contrib_objective(w):
            portfolio_var = w @ cov @ w
            marginal_contrib = cov @ w
            risk_contrib = w * marginal_contrib
            # Minimize variance of risk contributions
            return np.sum((risk_contrib - portfolio_var / n) ** 2)

        x0 = np.ones(n) / n
        bounds = [(0, self.constraints.get("max_weight_per_stock", 1.0)) for _ in range(n)]
        cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        result = minimize(risk_contrib_objective, x0, bounds=bounds,
                         constraints=cons, method="SLSQP",
                         options={"maxiter": 500, "ftol": 1e-12})
        if result.success:
            w = result.x
            return w / w.sum()
        return self._equal_weight(returns)  # fallback

    def _mean_variance(self, returns: pd.DataFrame, scores: pd.DataFrame | None = None) -> np.ndarray:
        """Maximize w'*mu - lambda * w'*Cov*w subject to sum(w)=1, w>=0."""
        cov = self._cov(returns)
        n = len(cov)

        # Expected returns: use historical mean, optionally tilted by scores
        mu = returns.mean().values
        if scores is not None:
            # Blend historical mean with score-based expected return
            score_vals = scores.iloc[-1].values if len(scores) > 0 else np.zeros(n)
            score_vals = np.nan_to_num(score_vals, nan=0.0)
            if score_vals.std() > 1e-12:
                score_vals = (score_vals - score_vals.mean()) / score_vals.std()
            mu = 0.5 * mu / max(mu.std(), 1e-12) + 0.5 * score_vals

        risk_aversion = self.constraints.get("risk_aversion", 1.0)

        def objective(w):
            return -(w @ mu - risk_aversion * w @ cov @ w)

        x0 = np.ones(n) / n
        bounds = [(0, self.constraints.get("max_weight_per_stock", 1.0)) for _ in range(n)]
        cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        # Turnover constraint
        if self._prev_weights is not None and self.constraints.get("max_turnover"):
            max_to = self.constraints["max_turnover"]
            cons.append({"type": "ineq", "fun": lambda w: max_to - np.sum(np.abs(w - self._prev_weights)) / 2})

        result = minimize(objective, x0, bounds=bounds, constraints=cons, method="SLSQP")
        if result.success:
            w = result.x
            w[w < 0] = 0
            return w / w.sum() if w.sum() > 0 else self._equal_weight(returns)
        return self._equal_weight(returns)

    def _max_sharpe(self, returns: pd.DataFrame, scores: pd.DataFrame | None = None) -> np.ndarray:
        """Maximize Sharpe ratio: w'*mu / sqrt(w'*Cov*w)."""
        cov = self._cov(returns)
        n = len(cov)
        mu = returns.mean().values
        if scores is not None:
            score_vals = scores.iloc[-1].values if len(scores) > 0 else np.zeros(n)
            score_vals = np.nan_to_num(score_vals, nan=0.0)
            if score_vals.std() > 1e-12:
                score_vals = (score_vals - score_vals.mean()) / score_vals.std()
            mu = 0.5 * mu / max(mu.std(), 1e-12) + 0.5 * score_vals

        def neg_sharpe(w):
            port_ret = w @ mu
            port_vol = np.sqrt(w @ cov @ w)
            return -port_ret / port_vol if port_vol > 1e-12 else 0.0

        x0 = np.ones(n) / n
        bounds = [(0, self.constraints.get("max_weight_per_stock", 1.0)) for _ in range(n)]
        cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        result = minimize(neg_sharpe, x0, bounds=bounds, constraints=cons, method="SLSQP")
        if result.success:
            w = result.x
            w[w < 0] = 0
            return w / w.sum() if w.sum() > 0 else self._equal_weight(returns)
        return self._equal_weight(returns)

    def _min_variance(self, returns: pd.DataFrame) -> np.ndarray:
        """Minimize w'*Cov*w subject to sum(w)=1, w>=0."""
        cov = self._cov(returns)
        n = len(cov)

        def objective(w):
            return w @ cov @ w

        x0 = np.ones(n) / n
        bounds = [(0, self.constraints.get("max_weight_per_stock", 1.0)) for _ in range(n)]
        cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        result = minimize(objective, x0, bounds=bounds, constraints=cons, method="SLSQP")
        if result.success:
            w = result.x
            return w / w.sum()
        return self._equal_weight(returns)

    def efficient_frontier(self, returns: pd.DataFrame, n_points: int = 20) -> list[dict]:
        """Compute efficient frontier points. Returns list of {volatility, return, sharpe, weights}."""
        cov = self._cov(returns)
        mu = returns.mean().values
        n = len(cov)
        x0 = np.ones(n) / n
        bounds = [(0, 1.0) for _ in range(n)]
        cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        min_var_result = minimize(lambda w: w @ cov @ w, x0, bounds=bounds, constraints=cons, method="SLSQP")
        if not min_var_result.success:
            return []
        min_var_w = min_var_result.x
        min_var_ret = min_var_w @ mu
        min_var_vol = np.sqrt(min_var_w @ cov @ min_var_w)

        max_ret_idx = np.argmax(mu)
        max_ret_w = np.zeros(n)
        max_ret_w[max_ret_idx] = 1.0
        max_ret = mu[max_ret_idx]

        points = []
        for target_ret in np.linspace(min_var_ret, max_ret, n_points):
            cons_target = cons + [{"type": "eq", "fun": lambda w, t=target_ret: w @ mu - t}]
            result = minimize(lambda w: w @ cov @ w, x0, bounds=bounds, constraints=cons_target, method="SLSQP")
            if result.success:
                w = result.x
                vol = np.sqrt(w @ cov @ w)
                ret = w @ mu
                points.append({
                    "volatility": round(float(vol), 6),
                    "expected_return": round(float(ret), 6),
                    "sharpe_ratio": round(float(ret / vol) if vol > 0 else 0, 6),
                    "weights": [round(float(x), 4) for x in w],
                })
        return points
