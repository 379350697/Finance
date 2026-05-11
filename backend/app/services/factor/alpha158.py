"""
Alpha158 factor set: 9 kbar + 4 price + 145 rolling = 158 factors.

Inspired by Qlib's Alpha158, adapted to the local OHLCV expression engine.
"""

from __future__ import annotations

from app.services.factor.expression import FactorExpression


class Alpha158:
    """158 factors: 9 kbar + 4 price + 145 rolling."""

    # ── 9 Kbar formulas (open/high/low/close bar relationships) ──────────
    KBAR_FORMULAS: list[tuple[str, str]] = [
        ("KMID",  "($open + $close) / 2"),
        ("KLEN",  "$high - $low"),
        ("KMID2", "($high + $low) / 2 - ($high_1 + $low_1) / 2"),
        ("KUP",   "$high - max($open, $close)"),
        ("KUP2",  "delta($high, 1) - delta(max($open, $close), 1)"),
        ("KLOW",  "min($open, $close) - $low"),
        ("KLOW2", "delta(min($open, $close), 1) - delta($low, 1)"),
        ("KSFT",  "$close - $open"),
        ("KSFT2", "delta($close, 1) - delta($open, 1)"),
    ]

    # ── 4 Price factors at window 0 ───────────────────────────────────────
    PRICE_FEATURES: list[tuple[str, str]] = [
        ("OPEN",  "$open"),
        ("HIGH",  "$high"),
        ("LOW",   "$low"),
        ("VWAP",  "($high + $low + $close) / 3"),
    ]

    # ── Rolling operators and windows ─────────────────────────────────────
    ROLLING_OPERATORS: list[str] = [
        "ts_mean", "ts_std", "ts_max", "ts_min",
        "ts_corr", "ts_cov", "ts_rank",
        "delta", "slope", "rsqr", "residue",
        "ts_sum",
    ]

    ROLLING_WINDOWS: list[int] = [5, 10, 20, 30, 60]

    # Unary operators (single-series input).
    UNARY_OPS: set[str] = {
        "ts_mean", "ts_std", "ts_max", "ts_min",
        "ts_rank", "delta", "slope", "ts_sum",
    }

    # Binary operators (two-series input) applied to ($close, $volume).
    BINARY_OPS: set[str] = {"ts_corr", "ts_cov", "rsqr", "residue"}

    @classmethod
    def build_expressions(cls) -> list[FactorExpression]:
        """Build the full list of 158 FactorExpressions."""
        exprs: list[FactorExpression] = []

        # 9 kbar factors
        for name, formula in cls.KBAR_FORMULAS:
            exprs.append(FactorExpression(name, formula))

        # 4 price factors
        for name, formula in cls.PRICE_FEATURES:
            exprs.append(FactorExpression(name, formula))

        # ── Rolling factors: 145 total ────────────────────────────────────
        #   (a) Unary ops on $close, $volume, $open  →  8 × 3 × 5 = 120
        #   (b) Binary ops on ($close, $volume)       →  4 × 5     =  20
        #   (c) ts_corr($close, $open)                →  1 × 5     =   5
        #                                              Total       = 145

        unary_features = [
            ("$close",  "close"),
            ("$volume", "volume"),
            ("$open",   "open"),
        ]

        for var_ref, short_name in unary_features:
            for op_name in cls.ROLLING_OPERATORS:
                if op_name not in cls.UNARY_OPS:
                    continue
                for w in cls.ROLLING_WINDOWS:
                    formula = f"{op_name}({var_ref}, {w})"
                    fname = f"{op_name}_{short_name}_{w}"
                    exprs.append(FactorExpression(fname, formula))

        # Binary operators on ($close, $volume)
        for op_name in cls.ROLLING_OPERATORS:
            if op_name not in cls.BINARY_OPS:
                continue
            for w in cls.ROLLING_WINDOWS:
                formula = f"{op_name}($close, $volume, {w})"
                fname = f"{op_name}_close_volume_{w}"
                exprs.append(FactorExpression(fname, formula))

        # Additional ts_corr on ($close, $open) -- a standard Qlib pairing
        for w in cls.ROLLING_WINDOWS:
            formula = f"ts_corr($close, $open, {w})"
            fname = f"ts_corr_close_open_{w}"
            exprs.append(FactorExpression(fname, formula))

        return exprs
