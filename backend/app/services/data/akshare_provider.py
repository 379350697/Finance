from __future__ import annotations

import time as _time
from datetime import date, datetime
from typing import Any

from app.schemas.market import DailyBar, MinuteBar, StockInfo, StockQuote
from app.services.data.provider import MarketDataError


class AkshareProvider:
    name = "akshare"

    def __init__(self):
        self._quote_cache: dict[str, StockQuote] = {}
        self._quote_ts: float = 0
        self._quote_ttl: float = 3.0

    def list_stocks(self) -> list[StockInfo]:
        try:
            import akshare as ak

            frame = ak.stock_info_a_code_name()
            return [
                StockInfo(code=str(row["code"]), name=str(row["name"]))
                for _, row in frame.iterrows()
            ]
        except Exception as exc:  # pragma: no cover - live provider is integration-only
            raise MarketDataError(self.name, str(exc)) from exc

    def get_quote(self, code: str) -> StockQuote:
        now = _time.time()
        if now - self._quote_ts < self._quote_ttl and code in self._quote_cache:
            return self._quote_cache[code]
        try:
            import akshare as ak

            frame = ak.stock_zh_a_spot_em()
            self._quote_ts = _time.time()
            self._quote_cache = {}
            for _, row in frame.iterrows():
                c = str(row["代码"])
                self._quote_cache[c] = StockQuote(
                    code=c,
                    name=str(row["名称"]),
                    price=float(row["最新价"]),
                    change_pct=_optional_float(row.get("涨跌幅")),
                    volume=_optional_float(row.get("成交量")),
                    turnover=_optional_float(row.get("成交额")),
                )
            quote = self._quote_cache.get(code)
            if quote:
                return quote
            raise MarketDataError(self.name, f"Stock {code} not found in spot data")
        except MarketDataError:
            raise
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

    def get_minute_bars(self, code: str, start: date, end: date, period: str = "5") -> list[MinuteBar]:
        try:
            import akshare as ak

            frame = ak.stock_zh_a_hist(
                symbol=code,
                period=period,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust="",
            )
            bars: list[MinuteBar] = []
            for _, row in frame.iterrows():
                bars.append(
                    MinuteBar(
                        code=code,
                        trade_time=row["日期"],
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
