from __future__ import annotations

from datetime import date
from typing import Any

from app.schemas.market import DailyBar, StockQuote
from app.services.data.provider import MarketDataError


class AkshareProvider:
    name = "akshare"

    def get_quote(self, code: str) -> StockQuote:
        try:
            import akshare as ak

            frame = ak.stock_zh_a_spot_em()
            row = frame.loc[frame["代码"].astype(str) == code].iloc[0]
            return StockQuote(
                code=str(row["代码"]),
                name=str(row["名称"]),
                price=float(row["最新价"]),
                change_pct=_optional_float(row.get("涨跌幅")),
                volume=_optional_float(row.get("成交量")),
                turnover=_optional_float(row.get("成交额")),
            )
        except Exception as exc:  # pragma: no cover - live provider is integration-only
            raise MarketDataError(self.name, str(exc)) from exc

    def get_daily_bars(self, code: str, start: date, end: date) -> list[DailyBar]:
        try:
            import akshare as ak

            frame = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust="",
            )
            bars: list[DailyBar] = []
            for _, row in frame.iterrows():
                bars.append(
                    DailyBar(
                        code=code,
                        trade_date=row["日期"],
                        open=float(row["开盘"]),
                        high=float(row["最高"]),
                        low=float(row["最低"]),
                        close=float(row["收盘"]),
                        volume=_optional_float(row.get("成交量")),
                        turnover=_optional_float(row.get("成交额")),
                    )
                )
            return bars
        except Exception as exc:  # pragma: no cover - live provider is integration-only
            raise MarketDataError(self.name, str(exc)) from exc


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
