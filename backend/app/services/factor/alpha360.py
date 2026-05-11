"""
Alpha360 factor set: 6 raw features x 60 historical windows = 360 factors.

Each of the 6 base formulas is delayed by 0..59 periods, producing a total
of 360 unique factors that capture a deep lookback window.
"""

from __future__ import annotations

import re

from app.services.factor.expression import FactorExpression

# Regex matching $variable references: e.g. $close, $close_5
# Group 1 = base name (letters/underscore only, no digits)
# Group 2 = optional existing lag digits
_VAR_LAG_RE = re.compile(r"\$([a-zA-Z_]+)(?:_(\d+))?")


def _apply_delay(formula: str, d: int) -> str:
    """Shift every $variable reference in *formula* by *d* periods.

    ``$close`` with d=3 becomes ``$close_3``.
    ``$close_1`` with d=3 becomes ``$close_4``.
    """
    if d == 0:
        return formula

    def _replace(m: re.Match) -> str:
        base = m.group(1)
        existing = int(m.group(2)) if m.group(2) else 0
        return f"${base}_{existing + d}"

    return _VAR_LAG_RE.sub(_replace, formula)


class Alpha360:
    """360 factors: 6 raw features each delayed 0..59 periods."""

    RAW_FEATURES: list[tuple[str, str]] = [
        ("OPEN_norm",   "$open / $close"),
        ("HIGH_norm",   "$high / $close"),
        ("LOW_norm",    "$low / $close"),
        ("RET",         "$close / $close_1 - 1"),
        ("VOL_norm",    "$volume / ts_mean($volume, 20)"),
        ("VOL_RATIO",   "ts_mean($volume, 5) / ts_mean($volume, 20)"),
    ]

    WINDOWS: int = 60  # delay 0 .. 59

    @classmethod
    def build_expressions(cls) -> list[FactorExpression]:
        """Build all 360 FactorExpressions (6 raw x 60 delays)."""
        exprs: list[FactorExpression] = []
        for base_name, formula in cls.RAW_FEATURES:
            for d in range(cls.WINDOWS):
                delayed = _apply_delay(formula, d)
                fname = f"{base_name}_{d}"
                exprs.append(FactorExpression(fname, delayed))
        return exprs
