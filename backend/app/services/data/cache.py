import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from app.core.config import settings
from app.schemas.market import DailyBar
from app.services.data.akshare_provider import AkshareProvider

CACHE_DIR = Path("data/daily")


class ParquetCache:
    def __init__(self, provider: AkshareProvider | None = None):
        self.provider = provider or AkshareProvider()
        os.makedirs(CACHE_DIR, exist_ok=True)

    def _get_file_path(self, code: str) -> Path:
        return CACHE_DIR / f"{code}.parquet"

    def get_bars(self, code: str, start: date, end: date) -> list[DailyBar]:
        file_path = self._get_file_path(code)
        
        # If no cache exists, we fetch from provider and cache it
        if not file_path.exists():
            bars = self.provider.get_daily_bars(code, start, end)
            if bars:
                df = pd.DataFrame([bar.model_dump() for bar in bars])
                df.to_parquet(file_path)
            return bars

        # Load cache
        df = pd.read_parquet(file_path)
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        
        # Check if we have the required date range
        min_date = df["trade_date"].min()
        max_date = df["trade_date"].max()

        fetch_needed = False
        fetch_start = start
        fetch_end = end

        # Simplistic approach: if requested range is out of bounds, fetch missing parts
        # For a more robust approach, we just fetch what's missing and append.
        new_dfs = []
        if end > max_date:
            fetch_needed = True
            missing_start = max_date + timedelta(days=1)
            # Fetch from max_date+1 to requested end (or today if end is today)
            new_bars = self.provider.get_daily_bars(code, missing_start, end)
            if new_bars:
                new_dfs.append(pd.DataFrame([bar.model_dump() for bar in new_bars]))
        
        if start < min_date:
            fetch_needed = True
            missing_end = min_date - timedelta(days=1)
            new_bars = self.provider.get_daily_bars(code, start, missing_end)
            if new_bars:
                new_dfs.append(pd.DataFrame([bar.model_dump() for bar in new_bars]))

        if new_dfs:
            df = pd.concat([df, *new_dfs]).drop_duplicates(subset=["code", "trade_date"]).sort_values("trade_date")
            df.to_parquet(file_path)

        # Filter to requested range
        mask = (df["trade_date"] >= start) & (df["trade_date"] <= end)
        filtered_df = df[mask]
        
        return [DailyBar(**row) for row in filtered_df.to_dict("records")]

    def sync_all(self):
        """
        Sync all stocks. If first time, fetches 2 years of data.
        Otherwise fetches missing data up to today.
        """
        stocks = self.provider.list_stocks()
        end_date = date.today()
        # 2 years back for initial sync
        start_date = end_date - timedelta(days=730)
        
        for stock in stocks:
            try:
                self.get_bars(stock.code, start_date, end_date)
            except Exception as e:
                print(f"Error syncing {stock.code}: {e}")
