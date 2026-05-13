"""
Recursive-descent expression engine for alpha factor computation.

Supports:
  - Variables: $open, $high, $low, $close, $volume
  - Lagged refs: $close_5  (close 5 periods ago)
  - Arithmetic: + - * / ( )
  - Scalar: sqrt($x), pow2($x), inv($x)
  - Cross-sectional: scale($x), cs_rank($x), rank($x)
  - Unary: abs($x), log($x), sign($x)
  - Rolling unary: ts_mean($x, N), ts_std($x, N), ts_max($x, N),
                   ts_min($x, N), ts_sum($x, N), ts_rank($x, N),
                   ts_delay($x, N), ts_delta($x, N), ts_pct_change($x, N),
                   ts_quantile($x, N), ts_skew($x, N), ts_kurt($x, N),
                   ts_decay_linear($x, N), ts_argmax($x, N), ts_argmin($x, N),
                   ts_prod($x, N)
  - Rolling binary: ts_corr($x, $y, N), ts_cov($x, $y, N),
                    ts_regression($x, $y, N)
  - Other: delta($x, N), slope($x, N), rsqr($x, $y, N),
           residue($x, $y, N)
  - Group: group_rank($x), group_mean($x), group_std($x),
           group_zscore($x), group_quantile($x)
  - Logic: if_else($cond, $true, $false)
"""
from __future__ import annotations

import enum
import math
import re
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd


# ── tokenizer ──────────────────────────────────────────────────────────

class TokenKind(enum.Enum):
    NUMBER = "NUMBER"
    VAR = "VAR"
    OP = "OP"
    FUNC = "FUNC"
    LPAREN = "("
    RPAREN = ")"
    COMMA = ","
    EOF = "EOF"


@dataclass
class Token:
    kind: TokenKind
    value: str = ""
    lag: int = 0  # for VAR with _N suffix, e.g. $close_5 → lag=5

    def __repr__(self):
        if self.kind == TokenKind.VAR and self.lag:
            return f"Token(VAR, {self.value}, lag={self.lag})"
        return f"Token({self.kind}, {self.value!r})"


VAR_RE = re.compile(r"\$([a-zA-Z_][a-zA-Z0-9_]*)(?:_(\d+))?")
FUNC_NAMES = {
    "ts_mean", "ts_std", "ts_max", "ts_min", "ts_sum", "ts_rank",
    "ts_corr", "ts_cov",
    "delta", "slope",
    "rsqr", "residue",
    "rank", "abs", "log", "sign",
    # New in G2
    "sqrt", "pow2", "inv",
    "scale", "cs_rank",
    "ts_delay", "ts_delta", "ts_pct_change", "ts_quantile",
    "ts_skew", "ts_kurt", "ts_decay_linear",
    "ts_argmax", "ts_argmin", "ts_prod",
    "ts_regression",
    "group_rank", "group_mean", "group_std", "group_zscore", "group_quantile",
    "if_else",
}


def tokenize(formula: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    n = len(formula)
    while i < n:
        ch = formula[i]
        if ch.isspace():
            i += 1
            continue
        if ch in "+-*/()":
            tokens.append(Token(TokenKind.OP, ch) if ch in "+-*/" else Token(TokenKind(ch)))
            i += 1
            continue
        if ch == ",":
            tokens.append(Token(TokenKind.COMMA))
            i += 1
            continue
        if ch == "$":
            m = VAR_RE.match(formula, i)
            if m:
                name = m.group(1)
                lag = int(m.group(2)) if m.group(2) else 0
                tokens.append(Token(TokenKind.VAR, name, lag=lag))
                i = m.end()
                continue
            raise ValueError(f"Invalid variable reference at pos {i}: {formula[i:i+20]}")
        if ch.isdigit() or ch == ".":
            j = i
            while j < n and (formula[j].isdigit() or formula[j] == "."):
                j += 1
            tokens.append(Token(TokenKind.NUMBER, formula[i:j]))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (formula[j].isalnum() or formula[j] == "_"):
                j += 1
            name = formula[i:j]
            if name in FUNC_NAMES:
                tokens.append(Token(TokenKind.FUNC, name))
            else:
                raise ValueError(f"Unknown function: {name}")
            i = j
            continue
        raise ValueError(f"Unexpected character at pos {i}: {ch!r}")
    tokens.append(Token(TokenKind.EOF))
    return tokens


# ── AST nodes ──────────────────────────────────────────────────────────

class Expr:
    def eval(self, ctx: EvalContext) -> pd.Series:
        raise NotImplementedError


@dataclass
class Num(Expr):
    val: float

    def eval(self, ctx):
        return pd.Series(self.val, index=ctx.index, dtype=float)


@dataclass
class Var(Expr):
    name: str
    lag: int = 0

    def eval(self, ctx):
        col = ctx.df[self.name].astype(float)
        if self.lag:
            col = col.shift(self.lag)
        return col.values if isinstance(col, pd.Series) else col


@dataclass
class BinOp(Expr):
    left: Expr
    op: str
    right: Expr

    def eval(self, ctx):
        lhs = self.left.eval(ctx)
        rhs = self.right.eval(ctx)
        if self.op == "+":
            return lhs + rhs
        if self.op == "-":
            return lhs - rhs
        if self.op == "*":
            return lhs * rhs
        if self.op == "/":
            return lhs / rhs.replace(0, np.nan)
        raise ValueError(f"Unknown op: {self.op}")


@dataclass
class UnaryOp(Expr):
    op: str
    arg: Expr

    def eval(self, ctx):
        val = self.arg.eval(ctx)
        if self.op == "-":
            return -val
        if self.op == "+":
            return val
        raise ValueError(f"Unknown unary op: {self.op}")


@dataclass
class FuncCall(Expr):
    name: str
    args: list[Expr]

    def eval(self, ctx):
        fn = OPERATORS.get(self.name)
        if fn is None:
            raise ValueError(f"Unknown function: {self.name}")

        # Group operators need ctx.groups injected as the last argument
        if self.name.startswith("group_"):
            evaled = [a.eval(ctx) for a in self.args]
            if ctx.groups is None:
                raise ValueError(
                    f"Group operator '{self.name}' requires groups in EvalContext"
                )
            return fn(*evaled, ctx.groups)

        evaled = [a.eval(ctx) for a in self.args]
        return fn(*evaled)


# ── recursive-descent parser ───────────────────────────────────────────

class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    @property
    def cur(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def expect(self, kind: TokenKind, val: str = "") -> Token:
        t = self.cur
        if t.kind != kind or (val and t.value != val):
            raise ValueError(f"Expected {kind}{' '+val if val else ''}, got {t}")
        return self.advance()

    # expr := term (('+' | '-') term)*
    def expr(self) -> Expr:
        left = self.term()
        while self.cur.kind == TokenKind.OP and self.cur.value in "+-":
            op = self.advance().value
            right = self.term()
            left = BinOp(left, op, right)
        return left

    # term := factor (('*' | '/') factor)*
    def term(self) -> Expr:
        left = self.factor()
        while self.cur.kind == TokenKind.OP and self.cur.value in "*/":
            op = self.advance().value
            right = self.factor()
            left = BinOp(left, op, right)
        return left

    # factor := NUMBER | VAR | func_call | '(' expr ')' | ('+'|'-') factor
    def factor(self) -> Expr:
        t = self.cur

        if t.kind == TokenKind.NUMBER:
            self.advance()
            return Num(float(t.value))

        if t.kind == TokenKind.VAR:
            self.advance()
            return Var(t.value, t.lag)

        if t.kind == TokenKind.FUNC:
            return self.func_call()

        if t.kind == TokenKind.LPAREN:
            self.advance()
            e = self.expr()
            self.expect(TokenKind.RPAREN)
            return e

        if t.kind == TokenKind.OP and t.value in "+-":
            self.advance()
            return UnaryOp(t.value, self.factor())

        raise ValueError(f"Unexpected token: {t}")

    # func_call := FUNC '(' expr (',' expr)* ')'
    def func_call(self) -> Expr:
        name = self.advance().value
        self.expect(TokenKind.LPAREN)
        args = [self.expr()]
        while self.cur.kind == TokenKind.COMMA:
            self.advance()
            args.append(self.expr())
        self.expect(TokenKind.RPAREN)
        return FuncCall(name, args)


# ── evaluation context ─────────────────────────────────────────────────

@dataclass
class EvalContext:
    df: pd.DataFrame  # columns: open, high, low, close, volume; index: date or int
    index: pd.Index | None = None
    groups: pd.Series | None = None  # group labels for group_* operators (e.g. industry codes)

    def __post_init__(self):
        if self.index is None:
            self.index = self.df.index


# ── operator implementations ───────────────────────────────────────────

def _op_abs(x: pd.Series) -> pd.Series:
    return x.abs()


def _op_log(x: pd.Series) -> pd.Series:
    return np.log(x.replace(0, np.nan))


def _op_sign(x: pd.Series) -> pd.Series:
    return np.sign(x)


def _op_rank(x: pd.Series) -> pd.Series:
    """Cross-sectional rank (0-1)."""
    return x.rank(pct=True)


def _op_delta(x: pd.Series, n: float) -> pd.Series:
    return x - x.shift(int(n))


def _op_ts_mean(x: pd.Series, n: float) -> pd.Series:
    w = int(n)
    try:
        from app.services._cython import _CYTHON_AVAILABLE, rolling_mean_1d
        if _CYTHON_AVAILABLE:
            return pd.Series(
                rolling_mean_1d(x.values.astype(np.float64), w),
                index=x.index,
            )
    except Exception:
        pass
    return x.rolling(window=w, min_periods=max(1, w // 2)).mean()


def _op_ts_std(x: pd.Series, n: float) -> pd.Series:
    w = int(n)
    try:
        from app.services._cython import _CYTHON_AVAILABLE, rolling_std_1d
        if _CYTHON_AVAILABLE:
            return pd.Series(
                rolling_std_1d(x.values.astype(np.float64), w),
                index=x.index,
            )
    except Exception:
        pass
    return x.rolling(window=w, min_periods=max(1, w // 2)).std()


def _op_ts_max(x: pd.Series, n: float) -> pd.Series:
    return x.rolling(window=int(n), min_periods=max(1, int(n) // 2)).max()


def _op_ts_min(x: pd.Series, n: float) -> pd.Series:
    return x.rolling(window=int(n), min_periods=max(1, int(n) // 2)).min()


def _op_ts_sum(x: pd.Series, n: float) -> pd.Series:
    w = int(n)
    try:
        from app.services._cython import _CYTHON_AVAILABLE, rolling_sum_1d
        if _CYTHON_AVAILABLE:
            return pd.Series(
                rolling_sum_1d(x.values.astype(np.float64), w),
                index=x.index,
            )
    except Exception:
        pass
    return x.rolling(window=w, min_periods=max(1, w // 2)).sum()


def _op_ts_rank(x: pd.Series, n: float) -> pd.Series:
    """Rolling rank within window (0-1)."""
    return x.rolling(window=int(n), min_periods=max(1, int(n) // 2)).apply(
        lambda s: s.rank(pct=True).iloc[-1], raw=False
    )


def _op_ts_corr(x: pd.Series, y: pd.Series, n: float) -> pd.Series:
    return x.rolling(window=int(n), min_periods=max(1, int(n) // 2)).corr(y)


def _op_ts_cov(x: pd.Series, y: pd.Series, n: float) -> pd.Series:
    return x.rolling(window=int(n), min_periods=max(1, int(n) // 2)).cov(y)


def _op_slope(x: pd.Series, n: float) -> pd.Series:
    """Linear regression slope over last N periods."""
    w = int(n)

    def _slope(s):
        if len(s) < max(2, w // 2):
            return np.nan
        t = np.arange(len(s))
        return np.polyfit(t, s.values, 1)[0]

    return x.rolling(window=w, min_periods=max(2, w // 2)).apply(_slope, raw=False)


def _op_rsqr(x: pd.Series, y: pd.Series, n: float) -> pd.Series:
    """R-squared of x ~ alpha + beta * y over N periods."""
    w = int(n)
    result = pd.Series(np.nan, index=x.index)
    for i in range(w - 1, len(x)):
        xs = x.iloc[i - w + 1 : i + 1]
        ys = y.iloc[i - w + 1 : i + 1]
        mask = xs.notna() & ys.notna()
        if mask.sum() < max(2, w // 2):
            continue
        corr = xs.corr(ys)
        result.iloc[i] = corr ** 2 if not np.isnan(corr) else np.nan
    return result


def _op_residue(x: pd.Series, y: pd.Series, n: float) -> pd.Series:
    """Residual of x after regressing on y over N periods."""
    w = int(n)
    result = pd.Series(np.nan, index=x.index)
    for i in range(w - 1, len(x)):
        xs = x.iloc[i - w + 1 : i + 1]
        ys = y.iloc[i - w + 1 : i + 1]
        mask = xs.notna() & ys.notna()
        if mask.sum() < max(2, w // 2):
            continue
        beta = xs.cov(ys) / ys.var() if ys.var() > 0 else 0
        alpha = xs.mean() - beta * ys.mean()
        result.iloc[i] = xs.iloc[-1] - (alpha + beta * ys.iloc[-1])
    return result


# ── G2: scalar operators ──────────────────────────────────────────────────


def _op_sqrt(x: pd.Series) -> pd.Series:
    return np.sqrt(x.clip(lower=0))


def _op_pow2(x: pd.Series) -> pd.Series:
    return x ** 2


def _op_inv(x: pd.Series) -> pd.Series:
    return 1.0 / x.replace(0, np.nan)


# ── G2: cross-sectional ───────────────────────────────────────────────────


def _op_scale(x: pd.Series) -> pd.Series:
    std = x.std(ddof=1)
    return (x - x.mean()) / std if std and std > 1e-12 else pd.Series(0.0, index=x.index)


def _op_cs_rank(x: pd.Series) -> pd.Series:
    return x.rank(pct=True)


# ── G2: rolling unary ─────────────────────────────────────────────────────


def _op_ts_delay(x: pd.Series, n: float) -> pd.Series:
    return x.shift(int(n))


def _op_ts_delta(x: pd.Series, n: float) -> pd.Series:
    return x - x.shift(int(n))


def _op_ts_pct_change(x: pd.Series, n: float) -> pd.Series:
    return x.pct_change(periods=int(n))


def _op_ts_quantile(x: pd.Series, n: float) -> pd.Series:
    w = int(n)
    min_p = max(2, w // 2)

    def _decile(s):
        valid = s.dropna()
        if len(valid) < min_p:
            return np.nan
        q = pd.qcut(valid, 10, labels=False, duplicates="drop")
        return q.iloc[-1] / 9.0 if len(q) > 0 else np.nan

    return x.rolling(w, min_periods=min_p).apply(_decile, raw=False)


def _op_ts_skew(x: pd.Series, n: float) -> pd.Series:
    w = int(n)
    return x.rolling(w, min_periods=max(3, w // 2)).skew()


def _op_ts_kurt(x: pd.Series, n: float) -> pd.Series:
    w = int(n)
    return x.rolling(w, min_periods=max(4, w // 2)).kurt()


def _op_ts_decay_linear(x: pd.Series, n: float) -> pd.Series:
    w = int(n)
    weights = np.arange(1, w + 1, dtype=np.float64)
    weights = weights / weights.sum()

    def _wavg(s):
        valid = s.dropna()
        if len(valid) < max(2, w // 2):
            return np.nan
        wgt = weights[-len(valid):]
        return np.dot(valid.values, wgt)

    return x.rolling(w, min_periods=max(2, w // 2)).apply(_wavg, raw=False)


def _op_ts_argmax(x: pd.Series, n: float) -> pd.Series:
    w = int(n)
    min_p = max(2, w // 2)

    def _amax(s):
        valid = s.dropna()
        if len(valid) < min_p:
            return np.nan
        return float(np.argmax(valid.values))

    return x.rolling(w, min_periods=min_p).apply(_amax, raw=False)


def _op_ts_argmin(x: pd.Series, n: float) -> pd.Series:
    w = int(n)
    min_p = max(2, w // 2)

    def _amin(s):
        valid = s.dropna()
        if len(valid) < min_p:
            return np.nan
        return float(np.argmin(valid.values))

    return x.rolling(w, min_periods=min_p).apply(_amin, raw=False)


def _op_ts_prod(x: pd.Series, n: float) -> pd.Series:
    w = int(n)
    return x.rolling(w, min_periods=max(1, w // 2)).apply(np.prod, raw=True)


# ── G2: rolling binary ────────────────────────────────────────────────────


def _op_ts_regression(x: pd.Series, y: pd.Series, n: float) -> pd.Series:
    """Rolling beta: coefficient of x ~ y regression."""
    w = int(n)
    min_p = max(2, w // 2)

    def _beta(xy):
        if len(xy) < min_p:
            return np.nan
        xs = xy[:, 0]
        ys = xy[:, 1]
        mask = ~np.isnan(xs) & ~np.isnan(ys)
        if mask.sum() < min_p:
            return np.nan
        cov = np.cov(xs[mask], ys[mask], ddof=1)[0, 1]
        var_y = np.var(ys[mask], ddof=1)
        return cov / var_y if var_y > 1e-12 else 0.0

    df = pd.DataFrame({"x": x, "y": y})
    return df.rolling(w, min_periods=min_p).apply(_beta, raw=True)


# ── G2: group operators (groups injected from EvalContext) ─────────────────


def _op_group_rank(x: pd.Series, groups: pd.Series) -> pd.Series:
    df = pd.DataFrame({"x": x, "g": groups})
    return df.groupby("g")["x"].rank(pct=True)


def _op_group_mean(x: pd.Series, groups: pd.Series) -> pd.Series:
    df = pd.DataFrame({"x": x, "g": groups})
    return df.groupby("g")["x"].transform("mean")


def _op_group_std(x: pd.Series, groups: pd.Series) -> pd.Series:
    df = pd.DataFrame({"x": x, "g": groups})
    return df.groupby("g")["x"].transform("std")


def _op_group_zscore(x: pd.Series, groups: pd.Series) -> pd.Series:
    df = pd.DataFrame({"x": x, "g": groups})
    mean = df.groupby("g")["x"].transform("mean")
    std = df.groupby("g")["x"].transform("std").replace(0, 1)
    return (df["x"] - mean) / std


def _op_group_quantile(x: pd.Series, groups: pd.Series) -> pd.Series:
    df = pd.DataFrame({"x": x, "g": groups})
    return df.groupby("g")["x"].transform(lambda s: s.rank(pct=True))


# ── G2: logic ─────────────────────────────────────────────────────────────


def _op_if_else(cond: pd.Series, true_val: pd.Series, false_val: pd.Series) -> pd.Series:
    return pd.Series(
        np.where(cond.astype(bool).values, true_val.values, false_val.values),
        index=cond.index,
    )


OPERATORS: dict[str, Callable[..., pd.Series]] = {
    "abs": _op_abs,
    "log": _op_log,
    "sign": _op_sign,
    "rank": _op_rank,
    "delta": _op_delta,
    "ts_mean": _op_ts_mean,
    "ts_std": _op_ts_std,
    "ts_max": _op_ts_max,
    "ts_min": _op_ts_min,
    "ts_sum": _op_ts_sum,
    "ts_rank": _op_ts_rank,
    "ts_corr": _op_ts_corr,
    "ts_cov": _op_ts_cov,
    "slope": _op_slope,
    "rsqr": _op_rsqr,
    "residue": _op_residue,
    # G2: scalar
    "sqrt": _op_sqrt,
    "pow2": _op_pow2,
    "inv": _op_inv,
    # G2: cross-sectional
    "scale": _op_scale,
    "cs_rank": _op_cs_rank,
    # G2: rolling unary
    "ts_delay": _op_ts_delay,
    "ts_delta": _op_ts_delta,
    "ts_pct_change": _op_ts_pct_change,
    "ts_quantile": _op_ts_quantile,
    "ts_skew": _op_ts_skew,
    "ts_kurt": _op_ts_kurt,
    "ts_decay_linear": _op_ts_decay_linear,
    "ts_argmax": _op_ts_argmax,
    "ts_argmin": _op_ts_argmin,
    "ts_prod": _op_ts_prod,
    # G2: rolling binary
    "ts_regression": _op_ts_regression,
    # G2: group (arity=2, groups injected from ctx)
    "group_rank": _op_group_rank,
    "group_mean": _op_group_mean,
    "group_std": _op_group_std,
    "group_zscore": _op_group_zscore,
    "group_quantile": _op_group_quantile,
    # G2: logic
    "if_else": _op_if_else,
}


# ── public API ─────────────────────────────────────────────────────────

class FactorExpression:
    """A single factor defined by a formula string."""

    def __init__(self, name: str, formula: str):
        self.name = name
        self.formula = formula
        tokens = tokenize(formula)
        self._ast = Parser(tokens).expr()

    def evaluate(self, df: pd.DataFrame) -> pd.Series:
        """Evaluate this factor on a DataFrame with OHLCV columns."""
        ctx = EvalContext(df)
        result = self._ast.eval(ctx)
        result.name = self.name
        return result


class FactorSet:
    """Collection of FactorExpressions evaluated together."""

    def __init__(self, expressions: list[FactorExpression]):
        self.expressions = expressions

    def evaluate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return DataFrame with one column per factor, aligned to df index."""
        out = pd.DataFrame(index=df.index)
        for expr in self.expressions:
            out[expr.name] = expr.evaluate(df)
        return out
