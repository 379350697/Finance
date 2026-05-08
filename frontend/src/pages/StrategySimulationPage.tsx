import React, { FormEvent, useCallback, useEffect, useMemo, useState, ReactNode } from "react";
import { Play, RefreshCw, TrendingUp, AlertTriangle } from "lucide-react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import KLineChart from "../components/KLineChart";
import { usePolling } from "../hooks/usePolling";
import {
  BacktestResult,
  StrategyRun,
  PaperOrder,
  AccountStatus,
  PaperPosition,
  PaperStats,
  NetValuePoint,
  MinuteBar,
  listOrders,
  listStrategyRuns,
  runBacktest,
  runStrategy,
  getAccountStatus,
  resetAccount,
  listPositions,
  getPaperStats,
  getNetValue,
  settlePaperTrading,
  syncMarketData,
  pauseStrategyRun,
  resumeStrategyRun,
  terminateStrategyRun,
  getSyncStatus,
  getMarketBars,
  getMarketQuote,
} from "../api/client";

type Mode = "simulate" | "backtest";

const strategies = [
  { value: "trend_reversal", label: "趋势反转策略" },
  { value: "moving_average_breakout", label: "均线放量突破" },
  { value: "test_fast_execution", label: "快速测试闭环(首个股票即可)" },
];

const defaultStats: PaperStats = {
  total_assets: 1000000,
  balance: 1000000,
  initial_balance: 1000000,
  cumulative_pnl: 0,
  cumulative_pnl_pct: 0,
  annualized_return: 0,
  max_drawdown: 0,
  win_rate: 0,
  total_trades: 0,
  open_orders: 0,
  positions_market_value: 0,
};

export function StrategySimulationPage() {
  const [mode, setMode] = useState<Mode>("simulate");
  const [strategyName, setStrategyName] = useState("trend_reversal");
  const [runs, setRuns] = useState<StrategyRun[]>([]);
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [status, setStatus] = useState("加载中…");
  const [statusType, setStatusType] = useState<"loading" | "running" | "idle" | "error" | "warn">("loading");
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [orderPage, setOrderPage] = useState(1);
  const ORDERS_PER_PAGE = 5;

  // Confirmation modal state
  const [confirmAction, setConfirmAction] = useState<{
    title: string;
    message: string;
    onConfirm: () => void;
  } | null>(null);

  const displayStatus = useMemo(() => {
    const runningRuns = runs.filter(r => r.status === "running");
    const pausedRuns = runs.filter(r => r.status === "paused");
    const failedRuns = runs.filter(r => r.status === "failed");

    if (runningRuns.length > 0) {
      const totalMatched = runningRuns.reduce((sum, r) => sum + (r.matched_count || 0), 0);
      if (totalMatched > 0) return `运行中 · 匹配 ${totalMatched} 只`;
      return "运行中 · 扫描中…";
    }
    if (pausedRuns.length > 0) return "策略已暂停";
    if (failedRuns.length > 0) return `失败 ${failedRuns.length} 个任务`;
    return "待运行";
  }, [runs]);

  const displayStatusType = useMemo<typeof statusType>(() => {
    if (runs.some(r => r.status === "running")) return "running";
    if (runs.some(r => r.status === "failed")) return "error";
    if (runs.some(r => r.status === "paused")) return "warn";
    return "idle";
  }, [runs]);

  const [startDate, setStartDate] = useState("2026-01-01");
  const [endDate, setEndDate] = useState("2026-05-08");
  const [stockPool, setStockPool] = useState("000001,000002");
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [account, setAccount] = useState<AccountStatus | null>(null);

  const [stats, setStats] = useState<PaperStats>(defaultStats);
  const [chartData, setChartData] = useState<NetValuePoint[]>([]);
  const [holdings, setHoldings] = useState<PaperPosition[]>([]);
  const [syncCount, setSyncCount] = useState<number>(0);
  const [watchCode, setWatchCode] = useState("000001");

  const minuteBarsFetcher = useCallback(
    () => getMarketBars(watchCode).then((r) => r.bars),
    [watchCode],
  );
  const minuteBars = usePolling<MinuteBar[]>(minuteBarsFetcher, 30000) ?? [];

  const quoteFetcher = useCallback(() => getMarketQuote(watchCode), [watchCode]);
  const quote = usePolling(quoteFetcher, 5000);

  const livePositions = usePolling(() => listPositions().catch(() => []), 10000);
  const liveStats = usePolling(() => getPaperStats().catch(() => defaultStats), 10000);
  const liveChart = usePolling(() => getNetValue().catch(() => []), 30000);
  const liveRuns = usePolling(() => listStrategyRuns().catch(() => []), 10000);
  const liveOrders = usePolling(() => listOrders().catch(() => []), 10000);

  useEffect(() => {
    if (livePositions) { setHoldings(livePositions); setLastUpdated(new Date()); }
  }, [livePositions]);
  useEffect(() => {
    if (liveStats) setStats(liveStats);
  }, [liveStats]);
  useEffect(() => {
    if (liveChart) setChartData(liveChart);
  }, [liveChart]);
  useEffect(() => {
    if (liveRuns) { setRuns(liveRuns); setIsInitialLoading(false); }
  }, [liveRuns]);
  useEffect(() => {
    if (liveOrders) { setOrders(liveOrders); setOrderPage(1); }
  }, [liveOrders]);

  const stockCodes = useMemo(
    () =>
      stockPool
        .split(/[,，\s]+/)
        .map((code) => code.trim())
        .filter(Boolean),
    [stockPool],
  );

  const refresh = async () => {
    const [nextRuns, nextOrders, nextAccount, nextStats, nextChart, nextPositions, syncRes] = await Promise.all([
      listStrategyRuns(),
      listOrders(),
      getAccountStatus(),
      getPaperStats().catch(() => defaultStats),
      getNetValue().catch(() => []),
      listPositions().catch(() => []),
      getSyncStatus().catch(() => ({ cached_count: 0 })),
    ]);

    setRuns(nextRuns);
    setOrders(nextOrders);
    setAccount(nextAccount);
    setStats(nextStats);
    setChartData(nextChart);
    setHoldings(nextPositions);
    setSyncCount(syncRes.cached_count);
    setLastUpdated(new Date());
  };

  useEffect(() => {
    const timer = setInterval(() => {
      getSyncStatus().then(res => setSyncCount(res.cached_count)).catch(() => {});
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  async function handleReset() {
    setConfirmAction({
      title: "重置账户",
      message: "这将清空所有账户余额、订单记录和持仓数据。此操作不可撤销，确定继续吗？",
      onConfirm: async () => {
        setConfirmAction(null);
        setStatus("重置中");
        setStatusType("loading");
        try {
          const newAccount = await resetAccount();
          setAccount(newAccount);
        } catch (e) {
          console.warn("Failed to reset backend account, continuing with local reset", e);
        }
        setStats(defaultStats);
        setChartData([]);
        setHoldings([]);
        try { await refresh(); } catch {}
        setStatus("已重置");
        setStatusType("idle");
      },
    });
  }

  async function handleSettle() {
    setConfirmAction({
      title: "手动结算",
      message: "将以当日收盘价结算所有持仓订单，计算盈亏并更新账户余额。确定继续吗？",
      onConfirm: async () => {
        setConfirmAction(null);
        setStatus("结算中");
        setStatusType("loading");
        const today = new Date().toLocaleDateString('en-CA');
        try {
          const result = await settlePaperTrading(today);
          setStatus(`已结算 ${result.settled_count} 笔订单`);
          setStatusType("idle");
          await refresh();
        } catch {
          setStatus("结算失败");
          setStatusType("error");
        }
      },
    });
  }

  async function handleSync() {
    setStatus("同步中");
    setStatusType("loading");
    try {
      const response = await syncMarketData();
      setStatus(response.status);
      setStatusType("idle");
    } catch {
      setStatus("同步失败");
      setStatusType("error");
    }
  }

  async function handleRun(event: FormEvent) {
    event.preventDefault();
    setStatus("排队中");
    setStatusType("loading");
    const today = new Date().toLocaleDateString('en-CA');
    try {
      const run = await runStrategy(strategyName, today);
      setRuns((current) => [run, ...current]);
      await refresh();
      setStatus("已提交");
      setStatusType("running");
    } catch (e: any) {
      console.error(e);
      if (e.message?.includes("409")) {
        setStatus("策略可能已在运行中");
      } else {
        setStatus("提交失败 · " + (e.message || "网络错误"));
      }
      setStatusType("error");
    }
  }

  async function handleBacktest(event: FormEvent) {
    event.preventDefault();
    setStatus("回测中");
    setStatusType("loading");
    const result = await runBacktest({
      strategy_name: strategyName,
      start_date: startDate,
      end_date: endDate,
      stock_pool: stockCodes,
      initial_capital: 100_000,
      position_size: 10_000,
      holding_days: 1,
      strategy_params:
        strategyName === "trend_reversal"
          ? { profit_forecast: { is_profit_increase: true, forecast_type: "预增" } }
          : {},
      stocks: [],
    });
    setBacktestResult(result);
    setStatus("回测完成");
    setStatusType("idle");
  }

  useEffect(() => {
    refresh().catch(() => {
      setStatus("连接失败");
      setStatusType("error");
      setIsInitialLoading(false);
    });
  }, []);

  const statusPillClass =
    displayStatusType === "running" ? "status-pill"
    : displayStatusType === "error" ? "status-pill status-pill--error"
    : displayStatusType === "warn" ? "status-pill status-pill--warn"
    : displayStatusType === "loading" ? "status-pill"
    : "status-pill status-pill--idle";

  return (
    <section className={mode === "backtest" ? "tool-layout" : ""}>
      <div className="tool-main">
        {/* ── Header ────────────────────────────────────────── */}
        <header className="section-header page-enter">
          <div>
            <h2>策略模拟</h2>
            <p>策略运行 · 假盘记录 · 日线级历史回测</p>
          </div>
          <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            <span className={statusPillClass}>{displayStatus}</span>
            {lastUpdated && (
              <span className="last-updated">
                更新 {lastUpdated.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </span>
            )}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
              <button onClick={handleSync} type="button" title="从服务器同步全市场最新K线数据">
                <RefreshCw size={14} /> 同步历史数据
              </button>
              <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-tertiary)", marginTop: "4px" }}>
                已同步 {syncCount} 只股票
              </span>
            </div>
          </div>
        </header>

        {/* ── Account bar (backtest mode) ───────────────────── */}
        {mode === "backtest" && (
          <div className="account-bar page-enter">
            <div style={{ display: "flex", gap: "24px", alignItems: "center" }}>
              <div>
                <strong>初始资金</strong>
                <div className="account-value">{account ? account.initial_balance.toLocaleString() : "..."} 元</div>
              </div>
              <div>
                <strong>可用余额</strong>
                <div className="account-value account-value--accent">{account ? account.balance.toLocaleString() : "..."} 元</div>
              </div>
            </div>
            <button onClick={handleReset} type="button" title="重置账户余额和订单记录">
              <RefreshCw size={14} /> 重置账户
            </button>
          </div>
        )}

        <div className="segmented page-enter">
          <button
            aria-selected={mode === "simulate"}
            onClick={() => setMode("simulate")}
            type="button"
          >
            运行记录
          </button>
          <button
            aria-selected={mode === "backtest"}
            onClick={() => setMode("backtest")}
            type="button"
          >
            回测
          </button>
        </div>

        {/* ═══════════════════════════════════════════════════════
            SIMULATE MODE
           ═══════════════════════════════════════════════════════ */}
        {mode === "simulate" ? (
          <>
            {/* ── Actions ──────────────────────────────────── */}
            <div className="page-enter" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <h3 style={{ margin: 0, fontSize: "var(--font-size-lg)", fontFamily: "var(--font-display)", fontWeight: 700 }}>当前模拟资产</h3>
              <div style={{ display: "flex", gap: "8px" }}>
                <button onClick={handleSettle} type="button" style={{ padding: "6px 12px", minHeight: "32px", fontSize: "var(--font-size-sm)" }}>
                  <TrendingUp size={14} /> 手动结算
                </button>
                <button onClick={handleReset} type="button" className="btn--danger" style={{ padding: "6px 12px", minHeight: "32px", fontSize: "var(--font-size-sm)" }}>
                  <RefreshCw size={14} /> 重置账户与记录
                </button>
              </div>
            </div>

            {/* ── Metrics Grid ─────────────────────────────── */}
            {isInitialLoading ? (
              <div className="metric-grid page-enter" style={{ gridTemplateColumns: "repeat(5, 1fr)" }}>
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="metric" style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", padding: "var(--space-md)", gap: "8px" }}>
                    <div className="skeleton" style={{ width: "60%", height: "10px" }} />
                    <div className="skeleton" style={{ width: "80%", height: "22px" }} />
                  </div>
                ))}
              </div>
            ) : (
              <div className="metric-grid page-enter" style={{ gridTemplateColumns: "repeat(5, 1fr)" }}>
                <Metric label="累计盈亏" value={
                  <span style={{ color: stats.cumulative_pnl === 0 ? "var(--text-primary)" : (stats.cumulative_pnl > 0 ? "var(--color-up)" : "var(--color-down)") }}>
                    ¥{stats.cumulative_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                } />
                <Metric label="年化收益率" value={
                  <span style={{ color: stats.annualized_return === 0 ? "var(--text-primary)" : (stats.annualized_return > 0 ? "var(--color-up)" : "var(--color-down)") }}>
                    {stats.annualized_return}%
                  </span>
                } />
                <Metric label="模拟资产" value={`¥${stats.total_assets.toLocaleString()}`} />
                <Metric label="最大回撤" value={`${stats.max_drawdown}%`} />
                <Metric label="策略胜率" value={`${stats.win_rate}%`} />
              </div>
            )}

            {/* ── K-Line Chart ─────────────────────────────── */}
            <div className="page-enter" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "16px 0 8px 0" }}>
              <h3 style={{ margin: 0, fontSize: "var(--font-size-lg)", fontFamily: "var(--font-display)", fontWeight: 700 }}>个股K线</h3>
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <select
                  value={watchCode}
                  onChange={(e) => setWatchCode(e.target.value)}
                  style={{
                    padding: "4px 8px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-subtle)",
                    background: "var(--bg-input)",
                    fontSize: "var(--font-size-sm)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  <option value="000001">000001 平安银行</option>
                  <option value="000002">000002 万科A</option>
                  <option value="600519">600519 贵州茅台</option>
                  {holdings.map((h) => (
                    <option key={h.stock_code} value={h.stock_code}>
                      {h.stock_code} {h.stock_name}
                    </option>
                  ))}
                </select>
                {quote && (
                  <span style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "var(--font-size-sm)",
                    fontWeight: 600,
                    color: (quote.change_pct ?? 0) >= 0 ? "var(--color-up)" : "var(--color-down)",
                  }}>
                    ¥{quote.price.toFixed(2)}
                  </span>
                )}
              </div>
            </div>

            <div className="chart-card page-enter" style={{ marginBottom: "var(--space-lg)" }}>
              <KLineChart bars={minuteBars} quote={quote} width={720} height={400} />
            </div>

            {/* ── Run Records ──────────────────────────────── */}
            <div className="page-enter" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "0 0 16px 0" }}>
              <h3 style={{ margin: 0, fontSize: "var(--font-size-lg)", fontFamily: "var(--font-display)", fontWeight: 700 }}>运行记录</h3>
              <form className="action-row" style={{ margin: 0 }} onSubmit={handleRun}>
                <StrategySelect value={strategyName} onChange={setStrategyName} />
                <button title="运行策略 (模拟盘实时运行)" type="submit">
                  <Play size={17} />
                  <span>运行</span>
                </button>
                <button title="刷新" type="button" onClick={() => refresh()}>
                  <RefreshCw size={17} />
                </button>
              </form>
            </div>

            <div className="table-wrap page-enter" style={{ marginBottom: "var(--space-lg)" }}>
              <table>
                <thead>
                  <tr>
                    <th>策略</th>
                    <th>交易日</th>
                    <th>状态</th>
                    <th>进度</th>
                    <th>任务 ID</th>
                    <th style={{ textAlign: "right" }}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: "center", color: "var(--text-tertiary)", padding: "40px 0" }}>
                        {isInitialLoading ? "加载中…" : "暂无策略运行记录"}
                        {!isInitialLoading && (
                          <div style={{ marginTop: "8px" }}>选择策略后点击「运行」开始模拟交易</div>
                        )}
                      </td>
                    </tr>
                  ) : (
                    runs.map((run) => {
                      const runOrders = orders.filter(o => o.run_id === run.id);
                      const isExpanded = expandedRunId === run.id;
                      return (
                        <React.Fragment key={run.id}>
                          <tr
                            onClick={() => setExpandedRunId(isExpanded ? null : run.id)}
                            style={{ cursor: "pointer" }}
                            className={isExpanded ? "run-row--expanded" : ""}
                          >
                            <td style={{ fontFamily: "var(--font-mono)", fontSize: "var(--font-size-sm)" }}>{run.display_name}</td>
                            <td style={{ fontFamily: "var(--font-mono)", fontSize: "var(--font-size-sm)" }}>{run.trade_date}</td>
                            <td>
                              <span className={`status-badge ${run.status}`}>
                                {run.status === "running" ? "运行中" : run.status === "paused" ? "已暂停" : run.status === "terminated" ? "已终止" : run.status === "failed" ? "失败" : "已完成"}
                              </span>
                            </td>
                            <td style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
                              {run.status === "running" && run.matched_count > 0
                                ? `匹配 ${run.matched_count} 只`
                                : run.status === "running"
                                ? "扫描中"
                                : run.status === "completed"
                                ? "—"
                                : run.status === "failed"
                                ? run.error_message
                                  ? "失败" + (run.error_message.length > 20 ? run.error_message.slice(0, 20) + "…" : run.error_message)
                                  : "—"
                                : "—"}
                            </td>
                            <td style={{ fontFamily: "var(--font-mono)", fontSize: "var(--font-size-xs)", color: "var(--text-tertiary)" }}>
                              {run.task_id.slice(0, 8)}
                            </td>
                            <td style={{ textAlign: "right" }}>
                              {run.status === "running" && (
                                <button
                                  type="button"
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    await pauseStrategyRun(run.id);
                                    refresh();
                                  }}
                                  style={{ padding: "4px 8px", fontSize: "var(--font-size-xs)", marginRight: "8px", minHeight: "auto", borderRadius: "4px" }}
                                >
                                  暂停
                                </button>
                              )}
                              {run.status === "paused" && (
                                <button
                                  type="button"
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    await resumeStrategyRun(run.id);
                                    refresh();
                                  }}
                                  className="btn--primary"
                                  style={{ padding: "4px 8px", fontSize: "var(--font-size-xs)", marginRight: "8px", minHeight: "auto", borderRadius: "4px" }}
                                >
                                  继续
                                </button>
                              )}
                              {(run.status === "running" || run.status === "paused") && (
                                <button
                                  type="button"
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    await terminateStrategyRun(run.id);
                                    refresh();
                                  }}
                                  className="btn--danger"
                                  style={{ padding: "4px 8px", fontSize: "var(--font-size-xs)", minHeight: "auto", borderRadius: "4px" }}
                                >
                                  终止
                                </button>
                              )}
                            </td>
                          </tr>
                          {isExpanded && (
                            <tr className="run-detail">
                              <td colSpan={6} style={{ padding: "16px 20px", background: "var(--bg-hover)", borderBottom: "1px solid var(--border-subtle)" }}>
                                {run.status === "failed" && run.error_message && (
                                  <div style={{ marginBottom: runOrders.length > 0 ? "12px" : 0, padding: "8px 12px", borderRadius: "var(--radius-sm)", background: "var(--color-down-bg)", color: "var(--color-down)", fontSize: "var(--font-size-sm)" }}>
                                    <strong>错误：</strong>{run.error_message}
                                  </div>
                                )}
                                {runOrders.length > 0 ? (
                                  <div>
                                    <div style={{ fontSize: "var(--font-size-sm)", fontWeight: 600, marginBottom: "8px", color: "var(--text-secondary)" }}>
                                      本次运行创建 {runOrders.length} 笔订单
                                    </div>
                                    <table style={{ margin: 0 }}>
                                      <thead>
                                        <tr>
                                          <th>股票</th>
                                          <th>方向</th>
                                          <th>价格</th>
                                          <th>数量</th>
                                          <th>盈亏</th>
                                          <th>状态</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {runOrders.map((o) => (
                                          <tr key={o.id}>
                                            <td>
                                              <div style={{ fontWeight: 600 }}>{o.stock_name}</div>
                                              <div style={{ fontSize: "var(--font-size-xs)", color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>{o.stock_code}</div>
                                            </td>
                                            <td>
                                              <span style={{
                                                color: o.side === "buy" ? "var(--color-up)" : "var(--color-down)",
                                                fontWeight: 600,
                                                fontSize: "var(--font-size-xs)",
                                                fontFamily: "var(--font-mono)",
                                              }}>
                                                {o.side === "buy" ? "买入" : "卖出"}
                                              </span>
                                            </td>
                                            <td style={{ fontFamily: "var(--font-mono)" }}>¥{o.entry_price.toFixed(2)}</td>
                                            <td style={{ fontFamily: "var(--font-mono)" }}>{o.quantity}</td>
                                            <td style={{ fontFamily: "var(--font-mono)", color: o.pnl >= 0 ? "var(--color-up)" : "var(--color-down)", fontWeight: 500 }}>
                                              {o.side === "sell" ? (
                                                <>{o.pnl >= 0 ? "+" : ""}¥{Math.abs(o.pnl).toLocaleString(undefined, { minimumFractionDigits: 2 })}</>
                                              ) : "—"}
                                            </td>
                                            <td>
                                              <span className={`status-badge ${o.status}`}>
                                                {o.status === "open" ? "持仓中" : o.status === "settled" ? "已结算" : o.status}
                                              </span>
                                            </td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                ) : run.status !== "failed" ? (
                                  <div style={{ fontSize: "var(--font-size-sm)", color: "var(--text-tertiary)" }}>
                                    暂无订单 — 策略未匹配到符合条件的股票
                                  </div>
                                ) : null}
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>

            {/* ── Today's Orders ────────────────────────────── */}
            <h3 className="page-enter" style={{ margin: "0 0 16px 0", fontSize: "var(--font-size-lg)", fontFamily: "var(--font-display)", fontWeight: 700 }}>
              今日订单
              {orders.length > 0 && (
                <span style={{ fontSize: "var(--font-size-sm)", fontWeight: 400, color: "var(--text-secondary)", marginLeft: "8px" }}>
                  ({orders.length} 笔)
                </span>
              )}
            </h3>
            <div className="table-wrap page-enter" style={{ marginBottom: "var(--space-lg)" }}>
              <table>
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>股票</th>
                    <th>方向</th>
                    <th>价格</th>
                    <th>数量</th>
                    <th>盈亏</th>
                    <th>状态</th>
                    <th>策略</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.length === 0 ? (
                    <tr>
                      <td colSpan={8} style={{ textAlign: "center", color: "var(--text-tertiary)", padding: "40px 0" }}>
                        暂无成交记录
                        <div style={{ marginTop: "8px", fontSize: "var(--font-size-xs)" }}>运行策略后自动生成订单</div>
                      </td>
                    </tr>
                  ) : (
                    orders.slice((orderPage - 1) * ORDERS_PER_PAGE, orderPage * ORDERS_PER_PAGE).map((o) => (
                      <tr key={o.id}>
                        <td style={{ fontSize: "var(--font-size-xs)", color: "var(--text-tertiary)", whiteSpace: "nowrap", fontFamily: "var(--font-mono)" }}>
                          {o.created_at ? new Date(o.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) : "—"}
                        </td>
                        <td>
                          <div style={{ fontWeight: 600 }}>{o.stock_name}</div>
                          <div style={{ fontSize: "var(--font-size-xs)", color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>{o.stock_code}</div>
                        </td>
                        <td>
                          <span style={{
                            display: "inline-block",
                            padding: "2px 8px",
                            borderRadius: "var(--radius-sm)",
                            fontSize: "var(--font-size-xs)",
                            fontWeight: 600,
                            fontFamily: "var(--font-mono)",
                            color: o.side === "buy" ? "var(--color-up)" : "var(--color-down)",
                            background: o.side === "buy" ? "var(--color-up-bg)" : "var(--color-down-bg)",
                          }}>
                            {o.side === "buy" ? "买入" : "卖出"}
                          </span>
                        </td>
                        <td style={{ fontFamily: "var(--font-mono)" }}>¥{o.entry_price.toFixed(2)}</td>
                        <td style={{ fontFamily: "var(--font-mono)" }}>{o.quantity}</td>
                        <td style={{ fontFamily: "var(--font-mono)", color: o.pnl >= 0 ? "var(--color-up)" : "var(--color-down)", fontWeight: 500 }}>
                          {o.status === "settled" ? (
                            <>{o.pnl >= 0 ? "+" : ""}¥{Math.abs(o.pnl).toLocaleString(undefined, { minimumFractionDigits: 2 })}</>
                          ) : "—"}
                        </td>
                        <td>
                          <span className={`status-badge ${o.status}`}>
                            {o.status === "open" ? "持仓中" : o.status === "settled" ? "已结算" : o.status}
                          </span>
                        </td>
                        <td style={{ fontSize: "var(--font-size-xs)", color: "var(--text-secondary)", maxWidth: "120px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {o.strategy_name}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              {orders.length > ORDERS_PER_PAGE && (
                <div style={{
                  display: "flex", alignItems: "center", justifyContent: "center",
                  gap: "6px", padding: "12px 16px",
                  borderTop: "1px solid var(--border-subtle)",
                }}>
                  <button
                    type="button"
                    onClick={() => setOrderPage((p) => Math.max(1, p - 1))}
                    disabled={orderPage === 1}
                    style={{ minHeight: "30px", padding: "0 10px", fontSize: "var(--font-size-xs)" }}
                  >
                    上一页
                  </button>
                  {Array.from({ length: Math.ceil(orders.length / ORDERS_PER_PAGE) }, (_, i) => i + 1).map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setOrderPage(p)}
                      style={{
                        minHeight: "30px", minWidth: "32px", padding: "0 8px",
                        fontSize: "var(--font-size-xs)", fontFamily: "var(--font-mono)",
                        background: orderPage === p ? "var(--text-primary)" : "var(--bg-card)",
                        color: orderPage === p ? "var(--text-inverse)" : "var(--text-secondary)",
                        borderColor: orderPage === p ? "var(--text-primary)" : "var(--border-subtle)",
                      }}
                    >
                      {p}
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={() => setOrderPage((p) => Math.min(Math.ceil(orders.length / ORDERS_PER_PAGE), p + 1))}
                    disabled={orderPage === Math.ceil(orders.length / ORDERS_PER_PAGE)}
                    style={{ minHeight: "30px", padding: "0 10px", fontSize: "var(--font-size-xs)" }}
                  >
                    下一页
                  </button>
                  <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-tertiary)", marginLeft: "8px" }}>
                    共 {orders.length} 条 · 第 {orderPage}/{Math.ceil(orders.length / ORDERS_PER_PAGE)} 页
                  </span>
                </div>
              )}
            </div>

            {/* ── Net Value + Holdings ──────────────────────── */}
            <div className="page-enter" style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)", gap: "var(--space-lg)", alignItems: "start" }}>
              <div className="chart-card">
                <h3 style={{ margin: "0 0 16px 0", fontSize: "var(--font-size-lg)", fontFamily: "var(--font-display)", fontWeight: 700 }}>净值走势</h3>
                <div style={{ height: "240px" }}>
                  {chartData.length === 0 ? (
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--text-tertiary)", flexDirection: "column", gap: "8px" }}>
                      <TrendingUp size={24} style={{ opacity: 0.3 }} />
                      <span>暂无净值数据 — 运行策略并结算后自动生成</span>
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chartData} margin={{ top: 5, right: 0, left: 0, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="var(--color-up)" stopOpacity={0.25} />
                            <stop offset="95%" stopColor="var(--color-up)" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 11, fontFamily: "var(--font-mono)", fill: "var(--text-secondary)" }} dy={10} />
                        <YAxis domain={['auto', 'auto']} hide />
                        <Tooltip
                          contentStyle={{
                            borderRadius: 'var(--radius-md)',
                            border: '1px solid var(--border-color)',
                            background: 'var(--bg-card)',
                            boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
                            fontFamily: 'var(--font-mono)',
                          }}
                          labelStyle={{ color: 'var(--text-secondary)', marginBottom: '4px' }}
                          itemStyle={{ color: 'var(--text-primary)', fontWeight: 600 }}
                          formatter={(value: number) => [`¥${value.toLocaleString()}`, "净值"]}
                        />
                        <Area type="monotone" dataKey="value" stroke="var(--color-up)" strokeWidth={2} fillOpacity={1} fill="url(#colorValue)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>

              <div>
                <h3 style={{ margin: "0 0 16px 0", fontSize: "var(--font-size-lg)", fontFamily: "var(--font-display)", fontWeight: 700 }}>
                  当前持仓
                  {holdings.length > 0 && (
                    <span style={{ fontSize: "var(--font-size-sm)", fontWeight: 400, color: "var(--text-secondary)", marginLeft: "8px" }}>
                      ({holdings.length} 只)
                    </span>
                  )}
                </h3>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>股票</th>
                        <th>数量</th>
                        <th>成本均价</th>
                        <th>市值</th>
                        <th>盈亏</th>
                      </tr>
                    </thead>
                    <tbody>
                      {holdings.length === 0 ? (
                        <tr>
                          <td colSpan={5} style={{ textAlign: "center", color: "var(--text-tertiary)", padding: "40px 0" }}>暂无持仓</td>
                        </tr>
                      ) : (
                        holdings.map((h) => (
                          <tr key={h.id}>
                            <td>
                              <div style={{ fontWeight: 600 }}>{h.stock_name}</div>
                              <div style={{ fontSize: "var(--font-size-xs)", color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>{h.stock_code}</div>
                            </td>
                            <td style={{ fontFamily: "var(--font-mono)" }}>{h.quantity}</td>
                            <td style={{ fontFamily: "var(--font-mono)" }}>{h.average_price.toFixed(2)}</td>
                            <td style={{ fontFamily: "var(--font-mono)" }}>¥{h.market_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                            <td style={{ fontFamily: "var(--font-mono)", color: h.pnl >= 0 ? "var(--color-up)" : "var(--color-down)", fontWeight: 500 }}>
                              {h.pnl >= 0 ? "+" : ""}¥{Math.abs(h.pnl).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </>
        ) : (
          /* ═══════════════════════════════════════════════════
             BACKTEST MODE
           ═══════════════════════════════════════════════════ */
          <BacktestPanel
            endDate={endDate}
            onSubmit={handleBacktest}
            result={backtestResult}
            setEndDate={setEndDate}
            setStartDate={setStartDate}
            setStockPool={setStockPool}
            setStrategyName={setStrategyName}
            startDate={startDate}
            stockPool={stockPool}
            strategyName={strategyName}
          />
        )}
      </div>

      {mode === "backtest" && (
        <aside className="context-panel">
          <h3>回测概览</h3>
          {backtestResult ? (
            <>
              <div className="metric">
                <span>交易数</span>
                <strong>{backtestResult.trade_count}</strong>
              </div>
              <div className="metric">
                <span>总收益</span>
                <strong style={{ color: backtestResult.total_return_pct >= 0 ? "var(--color-up)" : "var(--color-down)" }}>{backtestResult.total_return_pct}%</strong>
              </div>
              <div className="metric">
                <span>胜率</span>
                <strong>{(backtestResult.win_rate * 100).toFixed(0)}%</strong>
              </div>
              <div className="metric">
                <span>最大回撤</span>
                <strong>{backtestResult.max_drawdown_pct}%</strong>
              </div>
            </>
          ) : (
            <p style={{ color: "var(--text-tertiary)" }}>请配置参数并运行回测。</p>
          )}
        </aside>
      )}

      {/* ── Confirmation Modal ────────────────────────────── */}
      {confirmAction && (
        <div className="modal-overlay" onClick={() => setConfirmAction(null)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <h3><AlertTriangle size={18} style={{ verticalAlign: "middle", marginRight: "8px", color: "var(--color-warn)" }} />{confirmAction.title}</h3>
            <p>{confirmAction.message}</p>
            <div className="modal-actions">
              <button onClick={() => setConfirmAction(null)} type="button">取消</button>
              <button
                className="btn--danger"
                onClick={confirmAction.onConfirm}
                type="button"
              >
                确认
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function StrategySelect({
  onChange,
  value,
}: {
  onChange: (value: string) => void;
  value: string;
}) {
  return (
    <label>
      策略
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {strategies.map((strategy) => (
          <option key={strategy.value} value={strategy.value}>
            {strategy.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function BacktestPanel({
  endDate,
  onSubmit,
  result,
  setEndDate,
  setStartDate,
  setStockPool,
  setStrategyName,
  startDate,
  stockPool,
  strategyName,
}: {
  endDate: string;
  onSubmit: (event: FormEvent) => void;
  result: BacktestResult | null;
  setEndDate: (value: string) => void;
  setStartDate: (value: string) => void;
  setStockPool: (value: string) => void;
  setStrategyName: (value: string) => void;
  startDate: string;
  stockPool: string;
  strategyName: string;
}) {
  return (
    <>
      <form className="action-row page-enter" onSubmit={onSubmit}>
        <StrategySelect value={strategyName} onChange={setStrategyName} />
        <label>
          开始
          <input value={startDate} onChange={(event) => setStartDate(event.target.value)} type="date" />
        </label>
        <label>
          结束
          <input value={endDate} onChange={(event) => setEndDate(event.target.value)} type="date" />
        </label>
        <label className="wide-field">
          股票池
          <input value={stockPool} onChange={(event) => setStockPool(event.target.value)} placeholder="代码逗号分隔" />
        </label>
        <button title="运行回测" type="submit">
          <Play size={17} />
          <span>回测</span>
        </button>
      </form>

      {result && (
        <div className="backtest-results page-enter">
          <div className="metric-grid">
            <div className="metric">
              <span>总收益</span>
              <strong style={{ color: result.total_return_pct >= 0 ? "var(--color-up)" : "var(--color-down)" }}>{result.total_return_pct}%</strong>
            </div>
            <div className="metric">
              <span>胜率</span>
              <strong>{(result.win_rate * 100).toFixed(0)}%</strong>
            </div>
            <div className="metric">
              <span>最大回撤</span>
              <strong>{result.max_drawdown_pct}%</strong>
            </div>
            <div className="metric">
              <span>交易数</span>
              <strong>{result.trade_count}</strong>
            </div>
          </div>

          <h3 style={{ fontFamily: "var(--font-display)" }}>交易明细</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>股票</th>
                  <th>进场</th>
                  <th>出场</th>
                  <th>收益</th>
                  <th>原因</th>
                </tr>
              </thead>
              <tbody>
                {result.trades.map((trade) => (
                  <tr key={`${trade.stock_code}-${trade.entry_date}-${trade.exit_date}`}>
                    <td style={{ fontFamily: "var(--font-mono)" }}>{trade.stock_name ?? trade.stock_code}</td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>{trade.entry_date}</td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>{trade.exit_date}</td>
                    <td style={{ fontFamily: "var(--font-mono)", color: trade.return_pct >= 0 ? "var(--color-up)" : "var(--color-down)" }}>{trade.return_pct}%</td>
                    <td style={{ fontSize: "var(--font-size-sm)" }}>{trade.signal_reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3 style={{ fontFamily: "var(--font-display)" }}>每日收益</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>日期</th>
                  <th>当日收益</th>
                  <th>累计收益</th>
                  <th>交易数</th>
                </tr>
              </thead>
              <tbody>
                {result.daily_returns.map((daily) => (
                  <tr key={daily.trade_date}>
                    <td style={{ fontFamily: "var(--font-mono)" }}>{daily.trade_date}</td>
                    <td style={{ fontFamily: "var(--font-mono)", color: daily.return_pct >= 0 ? "var(--color-up)" : "var(--color-down)" }}>{daily.return_pct}%</td>
                    <td style={{ fontFamily: "var(--font-mono)", color: daily.cumulative_return_pct >= 0 ? "var(--color-up)" : "var(--color-down)" }}>{daily.cumulative_return_pct}%</td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>{daily.trades}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}

function Metric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
