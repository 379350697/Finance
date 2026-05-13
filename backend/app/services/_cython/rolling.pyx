# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
"""
Cython-accelerated rolling window functions.

Compile with: cythonize -i rolling.pyx
"""

import numpy as np
cimport numpy as np
cimport cython
from cython.parallel import prange

np.import_array()


# ---------------------------------------------------------------------------
# 1-D rolling functions (single time series)
# ---------------------------------------------------------------------------

@cython.boundscheck(False)
@cython.wraparound(False)
def rolling_mean_1d(
    np.ndarray[np.float64_t, ndim=1] x,
    int window,
    int min_periods = -1,
):
    """Rolling mean of a 1-D array."""
    cdef int n = x.shape[0]
    cdef int mp = min_periods if min_periods > 0 else max(1, window // 2)
    cdef np.ndarray[np.float64_t, ndim=1] out = np.full(n, np.nan, dtype=np.float64)
    cdef int i, j, count
    cdef double s
    cdef double val

    for i in range(mp - 1, n):
        s = 0.0
        count = 0
        for j in range(i - window + 1, i + 1):
            if j >= 0:
                val = x[j]
                if val == val:  # not NaN
                    s += val
                    count += 1
        if count >= mp:
            out[i] = s / count
    return out


@cython.boundscheck(False)
@cython.wraparound(False)
def rolling_std_1d(
    np.ndarray[np.float64_t, ndim=1] x,
    int window,
    int min_periods = -1,
    int ddof = 1,
):
    """Rolling standard deviation of a 1-D array."""
    cdef int n = x.shape[0]
    cdef int mp = min_periods if min_periods > 0 else max(2, window // 2)
    cdef np.ndarray[np.float64_t, ndim=1] out = np.full(n, np.nan, dtype=np.float64)
    cdef int i, j, count
    cdef double s, s2, val, mean, var
    cdef int d = ddof

    for i in range(mp - 1, n):
        s = 0.0
        s2 = 0.0
        count = 0
        for j in range(i - window + 1, i + 1):
            if j >= 0:
                val = x[j]
                if val == val:
                    s += val
                    s2 += val * val
                    count += 1
        if count > d and count >= mp:
            mean = s / count
            var = (s2 - count * mean * mean) / (count - d)
            if var > 0:
                out[i] = var ** 0.5
    return out


@cython.boundscheck(False)
@cython.wraparound(False)
def rolling_sum_1d(
    np.ndarray[np.float64_t, ndim=1] x,
    int window,
    int min_periods = -1,
):
    """Rolling sum of a 1-D array."""
    cdef int n = x.shape[0]
    cdef int mp = min_periods if min_periods > 0 else max(1, window // 2)
    cdef np.ndarray[np.float64_t, ndim=1] out = np.full(n, np.nan, dtype=np.float64)
    cdef int i, j, count
    cdef double s, val

    for i in range(mp - 1, n):
        s = 0.0
        count = 0
        for j in range(i - window + 1, i + 1):
            if j >= 0:
                val = x[j]
                if val == val:
                    s += val
                    count += 1
        if count >= mp:
            out[i] = s
    return out


# ---------------------------------------------------------------------------
# 2-D rolling functions (multiple columns, parallelized)
# ---------------------------------------------------------------------------

@cython.boundscheck(False)
@cython.wraparound(False)
def rolling_mean_2d(
    np.ndarray[np.float64_t, ndim=2] x,
    int window,
    int min_periods = -1,
):
    """Rolling mean along axis=0 for a 2-D array (n_times x n_feats)."""
    cdef int n = x.shape[0]
    cdef int p = x.shape[1]
    cdef int mp = min_periods if min_periods > 0 else max(1, window // 2)
    cdef np.ndarray[np.float64_t, ndim=2] out = np.full((n, p), np.nan, dtype=np.float64)
    cdef int i, j, k, count
    cdef double s, val

    for k in prange(p, nogil=True):
        for i in range(mp - 1, n):
            s = 0.0
            count = 0
            for j in range(i - window + 1, i + 1):
                if j >= 0:
                    val = x[j, k]
                    if val == val:
                        s += val
                        count += 1
            if count >= mp:
                out[i, k] = s / count
    return out


@cython.boundscheck(False)
@cython.wraparound(False)
def rolling_std_2d(
    np.ndarray[np.float64_t, ndim=2] x,
    int window,
    int min_periods = -1,
    int ddof = 1,
):
    """Rolling std along axis=0 for a 2-D array (n_times x n_feats)."""
    cdef int n = x.shape[0]
    cdef int p = x.shape[1]
    cdef int mp = min_periods if min_periods > 0 else max(2, window // 2)
    cdef np.ndarray[np.float64_t, ndim=2] out = np.full((n, p), np.nan, dtype=np.float64)
    cdef int i, j, k, count
    cdef double s, s2, val, mean, var
    cdef int d = ddof

    for k in prange(p, nogil=True):
        for i in range(mp - 1, n):
            s = 0.0
            s2 = 0.0
            count = 0
            for j in range(i - window + 1, i + 1):
                if j >= 0:
                    val = x[j, k]
                    if val == val:
                        s += val
                        s2 += val * val
                        count += 1
            if count > d and count >= mp:
                mean = s / count
                var = (s2 - count * mean * mean) / (count - d)
                if var > 0:
                    out[i, k] = var ** 0.5
    return out


@cython.boundscheck(False)
@cython.wraparound(False)
def rolling_sum_2d(
    np.ndarray[np.float64_t, ndim=2] x,
    int window,
    int min_periods = -1,
):
    """Rolling sum along axis=0 for a 2-D array (n_times x n_feats)."""
    cdef int n = x.shape[0]
    cdef int p = x.shape[1]
    cdef int mp = min_periods if min_periods > 0 else max(1, window // 2)
    cdef np.ndarray[np.float64_t, ndim=2] out = np.full((n, p), np.nan, dtype=np.float64)
    cdef int i, j, k, count
    cdef double s, val

    for k in prange(p, nogil=True):
        for i in range(mp - 1, n):
            s = 0.0
            count = 0
            for j in range(i - window + 1, i + 1):
                if j >= 0:
                    val = x[j, k]
                    if val == val:
                        s += val
                        count += 1
            if count >= mp:
                out[i, k] = s
    return out
