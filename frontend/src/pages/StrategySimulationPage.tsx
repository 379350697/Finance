import React, { FormEvent, useCallback, useEffect, useMemo, useState, ReactNode } from "react";
import { Play, RefreshCw, TrendingUp } from "lucide-react";
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
  const [status, setStatus] = useState("待运行");
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);

  const displayStatus = useMemo(() => {
    const runningRuns = runs.filter(r => r.status === "running");
    const pausedRuns = runs.filter(r => r.status === "paused");
    const failedRuns = runs.filter(r => r.status === "failed");

    if (runningRuns.length > 0) {
      const totalMatched = runningRuns.reduce((sum, r) => sum + (r.matched_count || 0), 0);
      if (totalMatched > 0) return `策略运行中，最近一轮匹配 ${totalMatched} 只`;
      return "策略运行中，扫描中…";
    }
    if (pausedRuns.length > 0) return "策略已暂停";
    if (failedRuns.length > 0) return `有 ${failedRuns.length} 个任务失败`;
    return "待运行";
  }, [runs]);
  const [startDate, setStartDate] = useState("2026-01-01");
  const [endDate, setEndDate] = useState("2026-03-20");
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
    if (livePositions) setHoldings(livePositions);
  }, [livePositions]);
  useEffect(() => {
    if (liveStats) setStats(liveStats);
  }, [liveStats]);
  useEffect(() => {
    if (liveChart) setChartData(liveChart);
  }, [liveChart]);
  useEffect(() => {
    if (liveRuns) setRuns(liveRuns);
  }, [liveRuns]);
  useEffect(() => {
    if (liveOrders) setOrders(liveOrders);
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
  };

  useEffect(() => {
    const timer = setInterval(() => {
      getSyncStatus().then(res => setSyncCount(res.cached_count)).catch(() => {});
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  async function handleReset() {
    setStatus("重置中");
    
    try {
      const newAccount = await resetAccount();
      setAccount(newAccount);
    } catch (e) {
      console.warn("Failed to reset backend account, continuing with local reset", e);
    }

    setStats(defaultStats);
    setChartData([]);
    setHoldings([]);

    try {
      await refresh();
    } catch (e) {
      console.warn("Failed to refresh backend after reset", e);
    }
    setStatus("已重置");
  }

  async function handleSettle() {
    setStatus("结算中");
    const today = new Date().toLocaleDateString('en-CA');
    try {
      const result = await settlePaperTrading(today);
      setStatus(`已结算 ${result.settled_count} 笔订单`);
      await refresh();
    } catch (e) {
      setStatus("结算失败");
    }
  }

  async function handleSync() {
    setStatus("同步中");
    try {
      const response = await syncMarketData();
      setStatus(response.status);
    } catch (e) {
      setStatus("同步失败");
    }
  }

  async function handleRun(event: FormEvent) {
    event.preventDefault();
    setStatus("排队中");
    const today = new Date().toLocaleDateString('en-CA'); // 'YYYY-MM-DD' local time
    try {
      const run = await runStrategy(strategyName, today);
      setRuns((current) => [run, ...current]);
      await refresh();
      setStatus("已提交");
    } catch (e: any) {
      console.error(e);
      if (e.message?.includes("409")) {
        setStatus("提交失败，策略可能已在运行中");
      } else {
        setStatus("提交失败，请检查网络或后台服务 (" + e.message + ")");
      }
    }
  }

  async function handleBacktest(event: FormEvent) {
    event.preventDefault();
    setStatus("回测中");
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
      stocks: [], // Backend will fetch real data
    });
    setBacktestResult(result);
    setStatus("回测完成");
  }

  useEffect(() => {
    refresh().catch(() => setStatus("连接失败"));
  }, []);

  return (
    <section className={mode === "backtest" ? "tool-layout" : ""}>
      <div className="tool-main">
        <header className="section-header">
          <div>
            <h2>策略模拟</h2>
            <p>策略运行、假盘记录和日线级历史回测</p>
          </div>
          <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            <span className="status-pill">{displayStatus}</span>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
              <button onClick={handleSync} type="button" title="从服务器同步全市场最新K线数据">
                <RefreshCw size={14} /> 同步历史数据
              </button>
              <span style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "4px" }}>
                已同步 {syncCount} 只股票
              </span>
            </div>
          </div>
        </header>

        {/* In simulate mode we use the new metrics grid instead of account bar */}
        {mode === "backtest" && (
          <div className="account-bar">
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

        <div className="segmented">
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

        {mode === "simulate" ? (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>当前模拟资产</h3>
              <div style={{ display: "flex", gap: "8px" }}>
                <button onClick={handleSettle} type="button" style={{ background: "var(--bg-card)", padding: "6px 12px", minHeight: "32px", fontSize: "13px" }}>
                  <TrendingUp size={14} /> 手动结算
                </button>
                <button onClick={handleReset} type="button" style={{ color: "var(--color-red)", background: "#fef2f2", padding: "6px 12px", minHeight: "32px", fontSize: "13px" }}>
                  <RefreshCw size={14} /> 重置账户与记录
                </button>
              </div>
            </div>
            
            <div className="metric-grid" style={{ gridTemplateColumns: "repeat(5, 1fr)" }}>
              <Metric label="累计盈亏" value={
                <span style={{ color: stats.cumulative_pnl === 0 ? "var(--text-primary)" : (stats.cumulative_pnl > 0 ? "var(--color-green)" : "var(--color-red)") }}>
                  ¥{stats.cumulative_pnl.toLocaleString(undefined, {minimumFractionDigits: 2})}
                </span>
              } />
              <Metric label="年化收益率" value={
                <span style={{ color: stats.annualized_return === 0 ? "var(--text-primary)" : (stats.annualized_return > 0 ? "var(--color-green)" : "var(--color-red)") }}>
                  {stats.annualized_return}%
                </span>
              } />
              <Metric label="模拟资产" value={`¥${stats.total_assets.toLocaleString()}`} />
              <Metric label="最大回撤" value={`${stats.max_drawdown}%`} />
              <Metric label="策略胜率" value={`${stats.win_rate}%`} />
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "16px 0 8px 0" }}>
              <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>个股K线</h3>
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <select
                  value={watchCode}
                  onChange={(e) => setWatchCode(e.target.value)}
                  style={{ padding: "4px 8px", borderRadius: "6px", border: "1px solid var(--border)", fontSize: "13px" }}
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
                    fontSize: "13px",
                    fontWeight: 600,
                    color: (quote.change_pct ?? 0) >= 0 ? "var(--color-red)" : "var(--color-green)",
                  }}>
                    ¥{quote.price.toFixed(2)}
                  </span>
                )}
              </div>
            </div>

            <div className="chart-card" style={{ background: "var(--bg-card)", borderRadius: "var(--radius-lg)", padding: "var(--space-lg)", boxShadow: "var(--shadow-card)", marginBottom: "var(--space-lg)" }}>
              <KLineChart bars={minuteBars} quote={quote} width={720} height={400} />
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "0 0 16px 0" }}>
              <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>运行记录</h3>
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

            <div className="table-wrap" style={{ marginBottom: "var(--space-lg)" }}>
              <table>
                <thead>
                  <tr>
                    <th>策略</th>
                    <th>交易日</th>
                    <th>状态</th>
                    <th>进度</th>
                    <th>任务</th>
                    <th style={{ textAlign: "right" }}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.length === 0 ? (
                    <tr>
                      <td colSpan={6}>暂无策略运行记录，选择策略后点击"运行"开始。</td>
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
                            <td>{run.display_name}</td>
                            <td>{run.trade_date}</td>
                            <td>
                              <span className={`status-badge ${run.status}`}>
                                {run.status === "running" ? "运行中" : run.status === "paused" ? "已暂停" : run.status === "terminated" ? "已终止" : run.status === "failed" ? "失败" : "已完成"}
                              </span>
                            </td>
                            <td style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
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
                            <td style={{ fontFamily: "monospace", fontSize: "12px", color: "var(--text-tertiary)" }}>
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
                                  style={{ padding: "4px 8px", fontSize: "12px", background: "var(--bg-card)", color: "var(--text-secondary)", border: "1px solid var(--border)", marginRight: "8px", minHeight: "auto", borderRadius: "4px" }}
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
                                  style={{ padding: "4px 8px", fontSize: "12px", background: "var(--bg-card)", color: "var(--color-green)", border: "1px solid var(--border)", marginRight: "8px", minHeight: "auto", borderRadius: "4px" }}
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
                                  style={{ padding: "4px 8px", fontSize: "12px", background: "var(--bg-card)", color: "var(--color-red)", border: "1px solid var(--border)", minHeight: "auto", borderRadius: "4px" }}
                                >
                                  终止
                                </button>
                              )}
                            </td>
                          </tr>
                          {isExpanded && (
                            <tr className="run-detail">
                              <td colSpan={6} style={{ padding: "16px 20px", background: "var(--bg-app)", borderBottom: "1px solid var(--border)" }}>
                                {run.status === "failed" && run.error_message && (
                                  <div style={{ marginBottom: runOrders.length > 0 ? "12px" : 0, padding: "8px 12px", borderRadius: "6px", background: "#fef2f2", color: "var(--color-red)", fontSize: "13px" }}>
                                    <strong>错误：</strong>{run.error_message}
                                  </div>
                                )}
                                {runOrders.length > 0 ? (
                                  <div>
                                    <div style={{ fontSize: "13px", fontWeight: 600, marginBottom: "8px", color: "var(--text-secondary)" }}>
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
                                              <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>{o.stock_code}</div>
                                            </td>
                                            <td>
                                              <span style={{
                                                color: o.side === "buy" ? "var(--color-red)" : "var(--color-green)",
                                                fontWeight: 600,
                                                fontSize: "12px",
                                              }}>
                                                {o.side === "buy" ? "买入" : "卖出"}
                                              </span>
                                            </td>
                                            <td>¥{o.entry_price.toFixed(2)}</td>
                                            <td>{o.quantity}</td>
                                            <td style={{ color: o.pnl >= 0 ? "var(--color-green)" : "var(--color-red)", fontWeight: 500 }}>
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
                                  <div style={{ fontSize: "13px", color: "var(--text-tertiary)" }}>
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

            <h3 style={{ margin: "0 0 16px 0", fontSize: "16px", fontWeight: 700 }}>
              今日订单
              {orders.length > 0 && (
                <span style={{ fontSize: "13px", fontWeight: 400, color: "var(--text-secondary)", marginLeft: "8px" }}>
                  ({orders.length} 笔)
                </span>
              )}
            </h3>
            <div className="table-wrap" style={{ marginBottom: "var(--space-lg)" }}>
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
                      <td colSpan={8} style={{ textAlign: "center", color: "var(--text-tertiary)", padding: "32px 0" }}>暂无成交记录 — 运行策略后自动生成</td>
                    </tr>
                  ) : (
                    orders.map((o) => (
                      <tr key={o.id}>
                        <td style={{ fontSize: "12px", color: "var(--text-tertiary)", whiteSpace: "nowrap" }}>
                          {o.created_at ? new Date(o.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) : "—"}
                        </td>
                        <td>
                          <div style={{ fontWeight: 600 }}>{o.stock_name}</div>
                          <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>{o.stock_code}</div>
                        </td>
                        <td>
                          <span style={{
                            display: "inline-block",
                            padding: "2px 8px",
                            borderRadius: "4px",
                            fontSize: "12px",
                            fontWeight: 600,
                            color: o.side === "buy" ? "var(--color-red)" : "var(--color-green)",
                            background: o.side === "buy" ? "#fef2f2" : "#f0fdf4",
                          }}>
                            {o.side === "buy" ? "买入" : "卖出"}
                          </span>
                        </td>
                        <td>¥{o.entry_price.toFixed(2)}</td>
                        <td>{o.quantity}</td>
                        <td style={{ color: o.pnl >= 0 ? "var(--color-green)" : "var(--color-red)", fontWeight: 500 }}>
                          {o.status === "settled" ? (
                            <>{o.pnl >= 0 ? "+" : ""}¥{Math.abs(o.pnl).toLocaleString(undefined, { minimumFractionDigits: 2 })}</>
                          ) : "—"}
                        </td>
                        <td>
                          <span className={`status-badge ${o.status}`}>
                            {o.status === "open" ? "持仓中" : o.status === "settled" ? "已结算" : o.status}
                          </span>
                        </td>
                        <td style={{ fontSize: "12px", color: "var(--text-secondary)", maxWidth: "120px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {o.strategy_name}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)", gap: "var(--space-lg)", alignItems: "start" }}>
              <div className="chart-card" style={{ background: "var(--bg-card)", borderRadius: "var(--radius-lg)", padding: "var(--space-lg)", boxShadow: "var(--shadow-card)" }}>
                <h3 style={{ margin: "0 0 16px 0", fontSize: "16px", fontWeight: 700 }}>净值走势</h3>
                <div style={{ height: "240px" }}>
                  {chartData.length === 0 ? (
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--text-tertiary)" }}>
                      <p>暂无净值数据 — 运行策略并结算后自动生成</p>
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chartData} margin={{ top: 5, right: 0, left: 0, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="var(--color-orange)" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="var(--color-orange)" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "var(--text-secondary)" }} dy={10} />
                        <YAxis domain={['auto', 'auto']} hide />
                        <Tooltip 
                          contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                          labelStyle={{ color: 'var(--text-secondary)', marginBottom: '4px' }}
                          itemStyle={{ color: 'var(--text-primary)', fontWeight: 600 }}
                          formatter={(value: number) => [`¥${value.toLocaleString()}`, "净值"]}
                        />
                        <Area type="monotone" dataKey="value" stroke="var(--color-orange)" strokeWidth={2} fillOpacity={1} fill="url(#colorValue)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>

              <div>
                <h3 style={{ margin: "0 0 16px 0", fontSize: "16px", fontWeight: 700 }}>
                  当前持仓
                  {holdings.length > 0 && (
                    <span style={{ fontSize: "13px", fontWeight: 400, color: "var(--text-secondary)", marginLeft: "8px" }}>
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
                              <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>{h.stock_code}</div>
                            </td>
                            <td>{h.quantity}</td>
                            <td>{h.average_price.toFixed(2)}</td>
                            <td>¥{h.market_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                            <td style={{ color: h.pnl >= 0 ? "var(--color-green)" : "var(--color-red)", fontWeight: 500 }}>
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
              <Metric label="交易数" value={backtestResult.trade_count} />
              <Metric label="总收益" value={`${backtestResult.total_return_pct}%`} />
              <Metric label="胜率" value={`${(backtestResult.win_rate * 100).toFixed(0)}%`} />
              <Metric label="最大回撤" value={`${backtestResult.max_drawdown_pct}%`} />
            </>
          ) : (
            <p>请配置参数并运行回测。</p>
          )}
        </aside>
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
      <form className="action-row" onSubmit={onSubmit}>
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
          <input value={stockPool} onChange={(event) => setStockPool(event.target.value)} />
        </label>
        <button title="运行回测" type="submit">
          <Play size={17} />
          <span>回测</span>
        </button>
      </form>

      {result && (
        <div className="backtest-results">
          <div className="metric-grid">
            <Metric label="总收益" value={`${result.total_return_pct}%`} />
            <Metric label="胜率" value={`${(result.win_rate * 100).toFixed(0)}%`} />
            <Metric label="最大回撤" value={`${result.max_drawdown_pct}%`} />
            <Metric label="交易数" value={result.trade_count} />
          </div>

          <h3>交易明细</h3>
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
                    <td>{trade.stock_name ?? trade.stock_code}</td>
                    <td>{trade.entry_date}</td>
                    <td>{trade.exit_date}</td>
                    <td>{trade.return_pct}%</td>
                    <td>{trade.signal_reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3>每日收益</h3>
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
                    <td>{daily.trade_date}</td>
                    <td>{daily.return_pct}%</td>
                    <td>{daily.cumulative_return_pct}%</td>
                    <td>{daily.trades}</td>
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

function buildBreakoutBars(code: string): DailyBar[] {
  const bars = Array.from({ length: 8 }, (_, index) => {
    const close = 10 + index * 0.1;
    return {
      code,
      trade_date: dateFrom("2026-01-01", index),
      open: close - 0.1,
      high: close + 0.2,
      low: close - 0.2,
      close,
      volume: 1000,
    };
  });
  bars[5] = { ...bars[5], close: 13, volume: 3000 };
  bars[6] = { ...bars[6], close: 14, volume: 1100 };
  return bars;
}

function buildTrendReversalBars(code: string): DailyBar[] {
  const bars = Array.from({ length: 70 }, (_, index) => {
    const close = 10 + index * 0.02;
    return {
      code,
      trade_date: dateFrom("2026-01-01", index),
      open: close - 0.05,
      high: close + 0.15,
      low: close - 0.15,
      close,
      volume: 1000,
    };
  });
  bars[60] = { ...bars[60], open: 12.2, close: 11.7 };
  bars[61] = { ...bars[61], open: 11.8, close: 11.2 };
  bars[62] = { ...bars[62], open: 11.3, close: 10.9 };
  bars[63] = { ...bars[63], open: 11.0, close: 12.6, high: 12.8, volume: 3000 };
  bars[64] = { ...bars[64], close: 13.1, high: 13.3 };
  return bars;
}

function dateFrom(start: string, offset: number) {
  const date = new Date(`${start}T00:00:00`);
  date.setDate(date.getDate() + offset);
  return date.toISOString().slice(0, 10);
}
