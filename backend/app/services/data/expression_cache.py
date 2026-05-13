"""ExpressionCache: hash-based cache for factor expression results."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime

import numpy as np
import pandas as pd

try:
    import h5py
except ImportError:
    h5py = None


class ExpressionCache:
    """Caches computed factor expression results as HDF5 files.

    Each cache entry is keyed by a SHA256 hash of
    (formula, sorted_codes, start_date, end_date).
    """

    def __init__(self, cache_dir: str = "data/cache/expressions", ttl_days: int = 7) -> None:
        if h5py is None:
            raise RuntimeError("h5py is required for ExpressionCache")
        self._cache_dir = cache_dir
        self._ttl_days = ttl_days
        self._hits = 0
        self._misses = 0
        os.makedirs(self._cache_dir, exist_ok=True)

    @staticmethod
    def _compute_key(formula: str, codes: list[str], start: date, end: date) -> str:
        payload = json.dumps(
            {
                "formula": formula,
                "codes": sorted(codes),
                "start": str(start),
                "end": str(end),
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _cache_path(self, key: str) -> str:
        subdir = os.path.join(self._cache_dir, key[:2])
        os.makedirs(subdir, exist_ok=True)
        return os.path.join(subdir, f"{key}.h5")

    def get(self, formula: str, codes: list[str], start: date, end: date) -> pd.DataFrame | None:
        """Return cached DataFrame or None if not found or stale."""
        key = self._compute_key(formula, codes, start, end)
        path = self._cache_path(key)
        if not os.path.exists(path):
            self._misses += 1
            return None

        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        if (datetime.now() - mtime).days > self._ttl_days:
            self._misses += 1
            return None

        try:
            with h5py.File(path, "r") as f:
                idx_raw = f["meta/index"][:]
                index_dates = [date.fromisoformat(d.decode() if isinstance(d, bytes) else d) for d in idx_raw]
                col_raw = f["meta/columns"][:]
                columns = [c.decode() if isinstance(c, bytes) else c for c in col_raw]
                values = f["data"][:]
            self._hits += 1
            return pd.DataFrame(values, index=pd.to_datetime(index_dates), columns=columns)
        except Exception:
            self._misses += 1
            return None

    def set(self, formula: str, codes: list[str], start: date, end: date, df: pd.DataFrame) -> None:
        """Write DataFrame to cache."""
        key = self._compute_key(formula, codes, start, end)
        path = self._cache_path(key)
        n_rows, n_cols = df.shape
        with h5py.File(path, "w") as f:
            f.create_dataset(
                "data",
                data=df.values.astype(np.float64),
                compression="gzip",
                compression_opts=1,
                chunks=(min(252, n_rows), min(100, n_cols)),
            )
            idx_str = np.array(
                [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in df.index],
                dtype="S10",
            )
            col_str = np.array([str(c)[:40] for c in df.columns], dtype="S40")
            f.create_dataset("meta/index", data=idx_str)
            f.create_dataset("meta/columns", data=col_str)

    def invalidate(self, older_than_days: int | None = None) -> int:
        """Remove stale cache entries. Returns count removed."""
        ttl = older_than_days if older_than_days is not None else self._ttl_days
        now = datetime.now()
        removed = 0
        for root, _dirs, files in os.walk(self._cache_dir):
            for fn in files:
                if fn.endswith(".h5"):
                    fp = os.path.join(root, fn)
                    if (now - datetime.fromtimestamp(os.path.getmtime(fp))).days > ttl:
                        os.remove(fp)
                        removed += 1
        return removed

    def stats(self) -> dict:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / max(1, self._hits + self._misses),
        }
