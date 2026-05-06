from __future__ import annotations

import time as _time
from datetime import date, datetime
from typing import Any

import requests

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
            market_code = 1 if code.startswith("6") else 0
            secid = f"{market_code}.{code}"
            url = "https://push2his.eastmoney.com/api/qt/stock/get"
            params = {
                "secid": secid,
                "fields": "f43,f44,f45,f46,f57,f58,f60,f170",
            }
            r = requests.get(url, params=params, timeout=10)
            data = r.json().get("data", {})
            if not data or "f57" not in data:
                raise MarketDataError(self.name, f"Stock {code} not found")
            price = float(data.get("f43", 0)) / 100
            pre_close = float(data.get("f60", 0)) / 100
            change_pct = round((price - pre_close) / pre_close * 100, 2) if pre_close > 0 else None
            quote = StockQuote(
                code=str(data["f57"]),
                name=str(data.get("f58", "")),
                price=price,
                change_pct=change_pct,
            )
            self._quote_ts = now
            self._quote_cache[code] = quote
            return quote
        except MarketDataError:
            raise
        except Exception as exc:
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

            start_str = f"{start.strftime('%Y-%m-%d')} 09:30:00"
            end_str = f"{end.strftime('%Y-%m-%d')} 15:00:00"
            frame = ak.stock_zh_a_hist_min_em(
                symbol=code,
                period=period,
                start_date=start_str,
                end_date=end_str,
                adjust="",
            )
            bars: list[MinuteBar] = []
            for _, row in frame.iterrows():
                bars.append(
                    MinuteBar(
                        code=code,
                        trade_time=row["时间"],
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
