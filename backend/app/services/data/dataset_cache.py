"""DatasetCache: caches preprocessed (X, y, dates, factor_names) bundles for model training."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime

import numpy as np


class DatasetCache:
    """Caches preprocessed model training datasets as compressed .npz files.

    Keyed by hash of (model_name, factor_set, train_start, train_end, stock_pool, label_type).
    """

    def __init__(self, cache_dir: str = "data/cache/datasets", ttl_days: int = 7) -> None:
        self._cache_dir = cache_dir
        self._ttl_days = ttl_days
        self._hits = 0
        self._misses = 0
        os.makedirs(self._cache_dir, exist_ok=True)

    def _compute_key(
        self,
        model_name: str,
        factor_set: str,
        train_start: date,
        train_end: date,
        stock_pool: list[str],
        label_type: str,
    ) -> str:
        payload = json.dumps(
            {
                "model": model_name,
                "factor_set": factor_set,
                "train_start": str(train_start),
                "train_end": str(train_end),
                "stock_pool": sorted(stock_pool),
                "label_type": label_type,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _cache_path(self, key: str) -> str:
        return os.path.join(self._cache_dir, f"{key}.npz")

    def get(
        self,
        model_name: str,
        factor_set: str,
        train_start: date,
        train_end: date,
        stock_pool: list[str],
        label_type: str,
    ) -> dict | None:
        """Return cached dataset dict or None if not found or stale."""
        key = self._compute_key(model_name, factor_set, train_start, train_end, stock_pool, label_type)
        path = self._cache_path(key)
        if not os.path.exists(path):
            self._misses += 1
            return None

        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        if (datetime.now() - mtime).days > self._ttl_days:
            self._misses += 1
            return None

        try:
            data = np.load(path, allow_pickle=True)
            result = {k: data[k] for k in data.files}
            self._hits += 1
            return result
        except Exception:
            self._misses += 1
            return None

    def set(
        self,
        model_name: str,
        factor_set: str,
        train_start: date,
        train_end: date,
        stock_pool: list[str],
        label_type: str,
        X: np.ndarray,
        y: np.ndarray,
        sample_dates: np.ndarray,
        factor_names: np.ndarray,
    ) -> None:
        """Write dataset to cache."""
        key = self._compute_key(model_name, factor_set, train_start, train_end, stock_pool, label_type)
        path = self._cache_path(key)
        np.savez_compressed(path, X=X, y=y, sample_dates=sample_dates, factor_names=factor_names)

    def invalidate(self, older_than_days: int | None = None) -> int:
        """Remove stale cache entries. Returns count removed."""
        ttl = older_than_days if older_than_days is not None else self._ttl_days
        now = datetime.now()
        removed = 0
        for fn in os.listdir(self._cache_dir):
            if fn.endswith(".npz"):
                fp = os.path.join(self._cache_dir, fn)
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
