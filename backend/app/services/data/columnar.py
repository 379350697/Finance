from __future__ import annotations

import time as _time
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import h5py
import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from app.services.data.service import MarketDataService

FIELD_NAMES = ["open", "high", "low", "close", "volume", "turnover"]
CACHE_DIR = Path("data/daily")


class ColumnarDataStore:
    """High-performance columnar data store backed by a single HDF5 file.

    Converts per-stock parquet files (data/daily/{code}.parquet) into
    a single columnar HDF5 file (data/columnar/daily.h5) where each
    field is stored as a 2D (n_dates, n_stocks) float64 dataset.
    """

    def __init__(self, store_path: str = "data/columnar") -> None:
        self._store_root = Path(store_path)
        self._store_root.mkdir(parents=True, exist_ok=True)
        self._file_path = self._store_root / "daily.h5"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_built(self) -> bool:
        if not self._file_path.exists():
            return False
        try:
            with h5py.File(self._file_path, "r") as f:
                return "/daily/close" in f
        except OSError:
            return False

    @property
    def codes(self) -> list[str]:
        if not self.is_built:
            return []
        with h5py.File(self._file_path, "r") as f:
            raw = f["/meta/codes"][:]
            return [
                c.decode("utf-8") if isinstance(c, bytes) else str(c) for c in raw
            ]

    @property
    def dates(self) -> list[date]:
        if not self.is_built:
            return []
        with h5py.File(self._file_path, "r") as f:
            raw = f["/meta/dates"][:]
            return [pd.Timestamp(d).date() for d in raw]

    # ------------------------------------------------------------------
    # Index resolution (shared across read methods)
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_indices(
        f: h5py.File,
        start: date | None,
        end: date | None,
        codes: list[str] | None,
    ) -> tuple[slice | np.ndarray, np.ndarray]:
        dates_arr: np.ndarray = f["/meta/dates"][:]
        raw_codes: np.ndarray = f["/meta/codes"][:]
        all_codes = [
            c.decode("utf-8") if isinstance(c, bytes) else str(c) for c in raw_codes
        ]

        if start is None and end is None:
            date_slice: slice | np.ndarray = slice(None)
        else:
            lo = 0
            hi = len(dates_arr)
            if start is not None:
                lo = max(lo, int(np.searchsorted(dates_arr, np.datetime64(start), side="left")))
            if end is not None:
                hi = min(hi, int(np.searchsorted(dates_arr, np.datetime64(end), side="right")))
            if lo >= hi:
                date_slice = np.array([], dtype=np.intp)
            else:
                date_slice = slice(lo, hi)

        if codes is None:
            code_indices = np.arange(len(all_codes), dtype=np.intp)
        else:
            code_map = {c: i for i, c in enumerate(all_codes)}
            code_indices = np.array(
                [code_map[c] for c in codes if c in code_map], dtype=np.intp
            )

        return date_slice, code_indices

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build_daily(
        self,
        codes: list[str] | None = None,
        start: date | None = None,
        end: date | None = None,
        market_data: MarketDataService | None = None,
    ) -> int:
        """Compile per-stock parquet files into a single columnar HDF5.

        Returns the number of stocks successfully written.
        """
        if codes:
            stock_codes = sorted(codes)
        else:
            stock_codes = sorted(f.stem for f in CACHE_DIR.glob("*.parquet"))

        if not stock_codes:
            return 0

        all_dates: set[date] = set()
        stock_data: dict[str, pd.DataFrame] = {}

        for code in stock_codes:
            fp = CACHE_DIR / f"{code}.parquet"
            if not fp.exists():
                continue
            df = pd.read_parquet(fp)
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
            if start is not None:
                df = df[df["trade_date"] >= start]
            if end is not None:
                df = df[df["trade_date"] <= end]
            if df.empty:
                continue
            stock_data[code] = df
            all_dates.update(df["trade_date"].values)

        if not all_dates:
            return 0

        sorted_dates = sorted(all_dates)
        date_idx = {d: i for i, d in enumerate(sorted_dates)}
        n_dates = len(sorted_dates)

        stock_codes = [c for c in stock_codes if c in stock_data]
        n_stocks = len(stock_codes)

        arrays: dict[str, np.ndarray] = {}
        for field in FIELD_NAMES:
            arr = np.full((n_dates, n_stocks), np.nan, dtype=np.float64)
            for ci, code in enumerate(stock_codes):
                sdf = stock_data[code]
                for _, row in sdf.iterrows():
                    di = date_idx[row["trade_date"]]
                    val = row.get(field)
                    if val is not None and not (isinstance(val, float) and np.isnan(val)):
                        arr[di, ci] = float(val)
            arrays[field] = arr

        max_code_len = max(len(c) for c in stock_codes)
        codes_bytes = np.array(
            [c.encode("utf-8") for c in stock_codes], dtype=f"S{max_code_len}"
        )
        dates_arr = np.array(sorted_dates, dtype="datetime64[ns]")

        with h5py.File(self._file_path, "w") as f:
            for field in FIELD_NAMES:
                f.create_dataset(
                    f"/daily/{field}",
                    data=arrays[field],
                    chunks=(252, min(100, n_stocks)),
                    compression="gzip",
                    compression_opts=1,
                    maxshape=(None, None),
                    dtype=np.float64,
                )
            f.create_dataset(
                "/meta/dates", data=dates_arr, maxshape=(None,), dtype=dates_arr.dtype
            )
            f.create_dataset(
                "/meta/codes", data=codes_bytes, maxshape=(None,), dtype=codes_bytes.dtype
            )

        return n_stocks

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def get_field(
        self,
        field: str,
        start: date | None = None,
        end: date | None = None,
        codes: list[str] | None = None,
    ) -> np.ndarray:
        """Return (n_dates, n_codes) float64 array for a single field."""
        with h5py.File(self._file_path, "r") as f:
            date_slice, code_indices = self._resolve_indices(f, start, end, codes)
            arr = f[f"/daily/{field}"][date_slice, :]
            return arr[:, code_indices].astype(np.float64, copy=False)

    def get_df(
        self,
        code: str,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        """Return single-stock OHLCV DataFrame with trade_date as DatetimeIndex."""
        with h5py.File(self._file_path, "r") as f:
            date_slice, code_indices = self._resolve_indices(f, start, end, [code])
            sliced_dates = f["/meta/dates"][date_slice]

            if len(code_indices) == 0 or len(sliced_dates) == 0:
                return pd.DataFrame(columns=FIELD_NAMES)

            ci = code_indices[0]
            data: dict[str, np.ndarray] = {}
            for field in FIELD_NAMES:
                data[field] = f[f"/daily/{field}"][date_slice, ci]

        df = pd.DataFrame(data)
        df.index = pd.DatetimeIndex(sliced_dates)
        df.index.name = "trade_date"
        return df

    def get_panel(
        self,
        fields: list[str] | None = None,
        start: date | None = None,
        end: date | None = None,
        codes: list[str] | None = None,
    ) -> np.ndarray:
        """Return (n_dates, n_stocks, n_fields) 3D float64 array."""
        if fields is None:
            fields = FIELD_NAMES

        with h5py.File(self._file_path, "r") as f:
            date_slice, code_indices = self._resolve_indices(f, start, end, codes)

            sliced_dates = f["/meta/dates"][date_slice]
            n_dates = len(sliced_dates)
            n_codes = len(code_indices)
            n_fields = len(fields)

            panel = np.full((n_dates, n_codes, n_fields), np.nan, dtype=np.float64)
            for fi, field in enumerate(fields):
                ds = f[f"/daily/{field}"]
                panel[:, :, fi] = ds[date_slice, :][:, code_indices]

            return panel

    # ------------------------------------------------------------------
    # Factors
    # ------------------------------------------------------------------

    def save_factors(
        self,
        factor_set: str,
        factor_names: list[str],
        factor_array: np.ndarray,
        dates: list[date],
        codes: list[str],
    ) -> str:
        """Save factors to ``data/columnar/factors/{factor_set}.h5``.

        ``factor_array`` must have shape (n_dates, n_stocks, n_factors).
        Returns the absolute path to the created file.
        """
        factor_dir = self._store_root / "factors"
        factor_dir.mkdir(parents=True, exist_ok=True)
        fp = factor_dir / f"{factor_set}.h5"

        codes_bytes = np.array(
            [c.encode("utf-8") for c in codes],
            dtype=f"S{max(len(c) for c in codes)}",
        )
        dates_arr = np.array(dates, dtype="datetime64[ns]")
        names_bytes = np.array(
            [n.encode("utf-8") for n in factor_names],
            dtype=f"S{max(len(n) for n in factor_names)}",
        )

        n_stocks = factor_array.shape[1]
        n_dates = factor_array.shape[0]

        with h5py.File(fp, "w") as f:
            for fi, name in enumerate(factor_names):
                f.create_dataset(
                    f"/factors/{name}",
                    data=factor_array[:, :, fi].astype(np.float64),
                    chunks=(min(252, n_dates), min(100, n_stocks)),
                    compression="gzip",
                    compression_opts=1,
                    maxshape=(None, None),
                    dtype=np.float64,
                )
            f.create_dataset("/meta/dates", data=dates_arr, maxshape=(None,))
            f.create_dataset("/meta/codes", data=codes_bytes, maxshape=(None,))
            f.create_dataset("/meta/factor_names", data=names_bytes, maxshape=(None,))

        return str(fp.resolve())

    def load_factors(
        self,
        factor_set: str,
        factor_names: list[str] | None = None,
        start: date | None = None,
        end: date | None = None,
        codes: list[str] | None = None,
    ) -> tuple[list[str], np.ndarray]:
        """Load factors from a factor set file.

        Returns ``(factor_names, array_3d)`` where the array has shape
        ``(n_dates, n_codes, n_factors)``.
        """
        fp = self._store_root / "factors" / f"{factor_set}.h5"
        if not fp.exists():
            raise FileNotFoundError(f"Factor set not found: {fp}")

        with h5py.File(fp, "r") as f:
            raw_names = f["/meta/factor_names"][:]
            all_names = [
                n.decode("utf-8") if isinstance(n, bytes) else str(n)
                for n in raw_names
            ]

            selected = factor_names if factor_names is not None else all_names
            date_slice, code_indices = self._resolve_indices(
                f, start, end, codes
            )
            sliced_dates = f["/meta/dates"][date_slice]
            n_dates = len(sliced_dates)
            n_codes = len(code_indices)
            n_fields = len(selected)

            result = np.full((n_dates, n_codes, n_fields), np.nan, dtype=np.float64)
            for fi, name in enumerate(selected):
                if f"/factors/{name}" not in f:
                    continue
                ds = f[f"/factors/{name}"]
                result[:, :, fi] = ds[date_slice, :][:, code_indices]

            return selected, result

    # ------------------------------------------------------------------
    # Incremental update
    # ------------------------------------------------------------------

    def update_daily(self, codes: list[str] | None = None) -> int:
        """Append new dates to the existing HDF5 from per-stock parquet files.

        If any requested code does not exist in the store, falls back to
        a full ``build_daily`` for those codes. Returns the number of
        stocks that contributed new observations.
        """
        if not self.is_built:
            if codes:
                return self.build_daily(codes=codes)
            return 0

        existing_codes = self.codes
        existing_dates_set = set(self.dates)
        last_existing = max(self.dates)

        if codes:
            unknown = [c for c in codes if c not in existing_codes]
            check_codes = [c for c in codes if c in existing_codes]
            if unknown and not check_codes:
                return self.build_daily(codes=codes)
            if unknown:
                return self.build_daily(codes=codes)
        else:
            check_codes = existing_codes

        all_new_dates: set[date] = set()
        code_updates: dict[str, pd.DataFrame] = {}

        for code in check_codes:
            fp = CACHE_DIR / f"{code}.parquet"
            if not fp.exists():
                continue
            df = pd.read_parquet(fp)
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
            new = df[df["trade_date"] > last_existing]
            if not new.empty:
                code_updates[code] = new
                all_new_dates.update(new["trade_date"].values)

        if not all_new_dates:
            return 0

        sorted_new_dates = sorted(all_new_dates)
        new_date_map = {d: i for i, d in enumerate(sorted_new_dates)}
        n_new = len(sorted_new_dates)
        n_stocks = len(existing_codes)

        append_arrays: dict[str, np.ndarray] = {}
        for field in FIELD_NAMES:
            arr = np.full((n_new, n_stocks), np.nan, dtype=np.float64)
            for ci, code in enumerate(existing_codes):
                if code not in code_updates:
                    continue
                sdf = code_updates[code]
                for _, row in sdf.iterrows():
                    di = new_date_map[row["trade_date"]]
                    val = row.get(field)
                    if val is not None and not (isinstance(val, float) and np.isnan(val)):
                        arr[di, ci] = float(val)
            append_arrays[field] = arr

        new_dates_arr = np.array(sorted_new_dates, dtype="datetime64[ns]")

        with h5py.File(self._file_path, "a") as f:
            for field in FIELD_NAMES:
                ds = f[f"/daily/{field}"]
                old_rows, _ = ds.shape
                ds.resize((old_rows + n_new, ds.shape[1]))
                ds[-n_new:, :] = append_arrays[field]

            dates_ds = f["/meta/dates"]
            old_rows = dates_ds.shape[0]
            dates_ds.resize((old_rows + n_new,))
            dates_ds[-n_new:] = new_dates_arr

        return len(code_updates)

    # ------------------------------------------------------------------
    # Benchmark
    # ------------------------------------------------------------------

    def benchmark(self) -> dict:
        """Measure HDF5 columnar read vs per-stock parquet read.

        Reads all fields for all stocks and compares wall-clock
        latency. Returns a dictionary with timing in milliseconds
        and the computed speedup factor.
        """
        if not self.is_built:
            return {"error": "Columnar store not built. Call build_daily() first."}

        # --- HDF5 read ---
        t0 = _time.perf_counter()
        panel = self.get_panel()
        t1 = _time.perf_counter()
        hdf5_ms = (t1 - t0) * 1000
        panel_elements = int(panel.shape[0]) * int(panel.shape[1]) * int(panel.shape[2])

        # --- Per-stock parquet read ---
        t2 = _time.perf_counter()
        frames: list[pd.DataFrame] = []
        for fpath in sorted(CACHE_DIR.glob("*.parquet")):
            df = pd.read_parquet(fpath)
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
            df = df.set_index(["trade_date", "code"])
            frames.append(df)
        parquet_rows = sum(len(f) for f in frames)
        t3 = _time.perf_counter()
        parquet_ms = (t3 - t2) * 1000

        speedup = round(parquet_ms / hdf5_ms, 1) if hdf5_ms > 0 else float("inf")

        return {
            "hdf5_ms": round(hdf5_ms, 2),
            "parquet_ms": round(parquet_ms, 2),
            "speedup": speedup,
            "hdf5_elements": panel_elements,
            "parquet_rows": parquet_rows,
        }
