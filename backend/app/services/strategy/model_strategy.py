"""
TopkDropoutStrategy: model-driven strategy that buys top-K ranked stocks
each day and holds for a configurable period, with dropout logic.

Follows the ``BaseStrategy`` Protocol defined in
``app.services.strategy.engine``.

Inspired by Qlib's TopkDropoutStrategy.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from app.core.config import settings
from app.schemas.market import DailyBar
from app.schemas.strategy import StrategySignal


class TopkDropoutStrategy:
    """Model-driven Top-K strategy with dropout tolerance.

    Each day the model scores all stocks.  The top ``top_k`` stocks by
    descending score are selected.  Positions are held for ``holding_days``
    trading days.  If a held stock's rank falls below
    ``top_k + dropout_threshold`` during the holding period, it is
    dropped out early.

    Parameters
    ----------
    model_name : str
        Name of the trained model (used by ModelPredictor).
    top_k : int
        Number of top stocks to select each day.
    holding_days : int
        Number of trading days to hold a position.
    dropout_threshold : float
        Soft tolerance beyond top_k before early exit.
        e.g. threshold=0 means exit as soon as rank > top_k.
        threshold=5 means exit when rank > top_k + 5.
    predictor : ModelPredictor | None
        Optional pre-built predictor instance.  Created lazily if None.
    """

    name = "topk_dropout"
    display_name = "TopK模型驱动"

    def __init__(
        self,
        model_name: str,
        top_k: int = 30,
        holding_days: int = 5,
        dropout_threshold: float = 0.0,
        predictor: Any = None,
    ) -> None:
        self.model_name = model_name
        self.top_k = top_k or settings.default_top_k
        self.holding_days = holding_days or settings.default_holding_days
        self.dropout_threshold = dropout_threshold

        self._predictor = predictor
        self._rankings_cache: dict[date, pd.DataFrame] = {}

    @property
    def predictor(self) -> Any:
        """Lazy-initialised ModelPredictor."""
        if self._predictor is None:
            from app.services.model.predictor import ModelPredictor

            self._predictor = ModelPredictor()
        return self._predictor

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rank_stocks(
        self,
        codes: list[str],
        predict_date: date,
    ) -> pd.DataFrame:
        """Batch-predict scores for all *codes* on a single date and rank them.

        Returns
        -------
        pd.DataFrame
            Columns: ``code``, ``score``, ``rank``.
            Sorted by ``rank`` ascending (1 = highest score).
        """
        if predict_date in self._rankings_cache:
            return self._rankings_cache[predict_date]

        df = self.predictor.predict(
            model_name=self.model_name,
            codes=codes,
            predict_date=predict_date,
        )
        self._rankings_cache[predict_date] = df
        return df

    def evaluate(
        self,
        stock_code: str,
        bars: list[DailyBar],
        context: dict | None = None,
    ) -> StrategySignal:
        """Evaluate whether *stock_code* should be bought today.

        The *context* dict is expected to contain:
        - ``daily_rankings``: pd.DataFrame with columns ``code``, ``score``, ``rank``
          for today's date.
        - ``predict_date``: date of the current evaluation.
        - ``position_holds``: dict[code, int] tracking how many days each code
          has been held (for dropout logic).

        Returns
        -------
        StrategySignal
        """
        context = context or {}
        rankings = context.get("daily_rankings")
        predict_date = context.get("predict_date")

        # If no precomputed rankings, we can't score this stock
        if rankings is None or rankings.empty:
            return StrategySignal(
                stock_code=stock_code,
                strategy_name=self.name,
                matched=False,
                reason="No daily rankings available",
            )

        # Find stock in rankings
        match = rankings.loc[rankings["code"] == stock_code]
        if match.empty:
            return StrategySignal(
                stock_code=stock_code,
                strategy_name=self.name,
                matched=False,
                reason=f"{stock_code} not in ranked universe",
            )

        score = float(match.iloc[0]["score"])
        rank = int(match.iloc[0]["rank"])

        # Check if stock is in top-k
        in_topk = rank <= self.top_k

        # Check dropout: if already holding and rank has fallen too far
        position_holds: dict[str, int] = context.get("position_holds", {})
        if stock_code in position_holds and not in_topk:
            if self.should_dropout(stock_code, rank):
                return StrategySignal(
                    stock_code=stock_code,
                    strategy_name=self.name,
                    matched=False,
                    reason=f"Dropout: rank {rank} > top_k {self.top_k} + threshold {self.dropout_threshold}",
                    score=score,
                    metrics={"rank": rank, "score": score, "dropout": True},
                )

        return StrategySignal(
            stock_code=stock_code,
            strategy_name=self.name,
            matched=in_topk,
            reason=(
                f"Rank {rank}/{self.top_k}, score {score:.4f}"
                if in_topk
                else f"Rank {rank} outside top {self.top_k}"
            ),
            score=score,
            metrics={"rank": rank, "score": score},
        )

    def should_dropout(self, code: str, current_rank: int) -> bool:
        """Determine whether a held stock should be exited early.

        Returns True when the current rank exceeds ``top_k + dropout_threshold``.
        """
        return current_rank > self.top_k + self.dropout_threshold

    # ------------------------------------------------------------------
    # Helpers for bulk pre-computation (used by BacktestService)
    # ------------------------------------------------------------------

    def precompute_rankings(
        self,
        codes: list[str],
        dates: list[date],
    ) -> dict[date, pd.DataFrame]:
        """Pre-compute daily rankings for all dates (for backtesting).

        Uses predict_batch to compute all scores in one shot, then groups
        by date into per-date DataFrames.

        Returns
        -------
        dict[date, pd.DataFrame]
            Mapping from each date to a DataFrame with columns
            ``code``, ``score``, ``rank``.
        """
        if not dates or not codes:
            return {}

        min_date = min(dates)
        max_date = max(dates)

        try:
            batch_df = self.predictor.predict_batch(
                model_name=self.model_name,
                codes=codes,
                start_date=min_date,
                end_date=max_date,
            )
        except Exception:
            return {}

        result: dict[date, pd.DataFrame] = {}
        grouped = batch_df.groupby("date")
        for dt, group in grouped:
            # dt is pd.Timestamp from groupby
            dt_key = dt.date() if isinstance(dt, pd.Timestamp) else dt
            grp = group.drop(columns=["date"]).sort_values("rank").reset_index(drop=True)
            result[dt_key] = grp
            self._rankings_cache[dt_key] = grp

        return result
