"""
Cython-accelerated rolling window operations.

Graceful fallback: imports the compiled Cython module if available,
otherwise uses pure-Python implementations with identical signatures.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from app.services._cython.rolling import (  # type: ignore[import-untyped]
        rolling_mean_1d,
        rolling_mean_2d,
        rolling_std_1d,
        rolling_std_2d,
        rolling_sum_1d,
        rolling_sum_2d,
    )

    _CYTHON_AVAILABLE = True
    logger.debug("Cython rolling module loaded.")
except ImportError:
    from app.services._cython.rolling_py import (  # type: ignore[no-redef]
        rolling_mean_1d,
        rolling_mean_2d,
        rolling_std_1d,
        rolling_std_2d,
        rolling_sum_1d,
        rolling_sum_2d,
    )

    _CYTHON_AVAILABLE = False
    logger.debug("Cython rolling module not compiled; using Python fallback.")
