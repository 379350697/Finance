from __future__ import annotations

import random as _random
import time as _time
from datetime import date, datetime
from typing import Any

import requests

from app.schemas.market import DailyBar, MinuteBar, StockInfo, StockQuote
from app.services.data.provider import MarketDataError

# —— Rate limiter (module-level, shared by all API calls) ———
# eastmoney has no published rate-limit docs. AKShare's built-in pattern
# uses random.uniform(0.5, 1.5) between pages and exponential-backoff retry.
# We adopt the same window: 1.0 s floor + up to 0.5 s jitter.
_last_api_call: float = 0
_MIN_INTERVAL = 1.0
_MAX_JITTER = 0.5


def _throttle() -> None:
    global _last_api_call
    elapsed = _time.time() - _last_api_call
    if elapsed < _MIN_INTERVAL:
        _time.sleep(_MIN_INTERVAL - elapsed + _random.uniform(0, _MAX_JITTER))
    _last_api_call = _time.time()


# —— Shared session with browser-like headers (thwarts CDN bot detection) ———
_SESSION: requests.Session | None = None
_UT_TOKEN = "fa5fd1943c7b386f172d6893dbbd4dc1"  # eastmoney API auth token


def _get_session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://quote.eastmoney.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
    return _SESSION


# —— Quote API endpoints (ordered by preference) ———
_QUOTE_ENDPOINTS = [
    "https://push2his.eastmoney.com/api/qt/stock/get",
    "https://push2.eastmoney.com/api/qt/stock/get",
    "https://82.push2his.eastmoney.com/api/qt/stock/get",
    "https://82.push2.eastmoney.com/api/qt/stock/get",
]

# —— K-line API endpoints (ordered by preference) ———
_KLINE_ENDPOINTS = [
    "https://push2his.eastmoney.com/api/qt/stock/kline/get",
    "https://push2.eastmoney.com/api/qt/stock/kline/get",
    "https://82.push2his.eastmoney.com/api/qt/stock/kline/get",
    "https://82.push2.eastmoney.com/api/qt/stock/kline/get",
]

# —— Circuit breaker (endpoint → (consecutive_failures, cooldown_until_ts)) ———
_endpoint_failures: dict[str, tuple[int, float]] = {}
_COOLDOWN_S = 60
_MAX_FAILURES = 3


def _is_cooling_down(url: str) -> bool:
    failures, until = _endpoint_failures.get(url, (0, 0))
    return failures >= _MAX_FAILURES and _time.time() < until


def _mark_failure(url: str) -> None:
    failures, _ = _endpoint_failures.get(url, (0, 0))
    _endpoint_failures[url] = (failures + 1, _time.time() + _COOLDOWN_S)


def _mark_success(url: str) -> None:
    _endpoint_failures[url] = (0, 0)


class AkshareProvider:
    name = "akshare"

    def __init__(self):
        self._quote_cache: dict[str, StockQuote] = {}
        self._quote_ts: float = 0
        self._quote_ttl: float = 3.0

    # ——— list_stocks unchanged ———

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

    # ——— get_quote with multi-endpoint fallback ———

    def get_quote(self, code: str) -> StockQuote:
        now = _time.time()
        if now - self._quote_ts < self._quote_ttl and code in self._quote_cache:
            return self._quote_cache[code]

        market_code = 1 if code.startswith("6") else 0
        secid = f"{market_code}.{code}"
        params = {
            "secid": secid,
            "fields": "f43,f44,f45,f46,f57,f58,f60,f170",
            "ut": _UT_TOKEN,
        }

        last_error: Exception | None = None
        session = _get_session()
        for url in _QUOTE_ENDPOINTS:
            if _is_cooling_down(url):
                continue
            try:
                _throttle()
                r = session.get(url, params=params, timeout=10)
                data = r.json().get("data", {})
                if not data or "f57" not in data:
                    _mark_success(url)  # endpoint works, just bad symbol
                    raise MarketDataError(self.name, f"Stock {code} not found")
                _mark_success(url)
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
                last_error = exc
                _mark_failure(url)
                continue

        raise MarketDataError(self.name, str(last_error) if last_error else "All endpoints exhausted")

    # ——— get_daily_bars unchanged ———

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

    # ——— get_minute_bars with multi-endpoint fallback ———

    def get_minute_bars(self, code: str, start: date, end: date, period: str = "5") -> list[MinuteBar]:
        last_error: Exception | None = None

        # Primary: AKShare (which uses push2his internally, with built-in retry)
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
            last_error = exc
            # Fall through to direct HTTP fallback

        # Fallback: direct HTTP to K-line endpoints (bypasses AKShare)
        market_code = 1 if code.startswith("6") else 0
        secid = f"{market_code}.{code}"
        params = {
            "secid": secid,
            "klt": period,
            "fqt": "1",
            "beg": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "ut": _UT_TOKEN,
        }

        session = _get_session()
        for url in _KLINE_ENDPOINTS:
            if _is_cooling_down(url):
                continue
            try:
                _throttle()
                r = session.get(url, params=params, timeout=15)
                resp = r.json()
                klines = resp.get("data", {}).get("klines", [])
                if not klines:
                    _mark_success(url)
                    continue
                _mark_success(url)
                bars = []
                for k in klines:
                    fields = k.split(",")
                    if len(fields) < 7:
                        continue
                    bars.append(
                        MinuteBar(
                            code=code,
                            trade_time=fields[0],
                            open=float(fields[1]),
                            high=float(fields[3]),
                            low=float(fields[4]),
                            close=float(fields[2]),
                            volume=_optional_float(fields[5]),
                            turnover=_optional_float(fields[6]),
                        )
                    )
                return bars
            except Exception as exc:
                _mark_failure(url)
                last_error = exc
                continue

        raise MarketDataError(self.name, str(last_error) if last_error else "All K-line endpoints exhausted")


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
