import { FormEvent, useEffect, useMemo, useState } from "react";
import { Play, RefreshCw } from "lucide-react";
import {
  BacktestResult,
  DailyBar,
  StrategyRun,
  AccountStatus,
  listOrders,
  listStrategyRuns,
  runBacktest,
  runStrategy,
  getAccountStatus,
  resetAccount,
  syncMarketData,
} from "../api/client";

type Mode = "simulate" | "backtest";

const strategies = [
  { value: "trend_reversal", label: "趋势反转策略" },
  { value: "moving_average_breakout", label: "均线放量突破" },
];

export function StrategySimulationPage() {
  const [mode, setMode] = useState<Mode>("simulate");
  const [strategyName, setStrategyName] = useState("trend_reversal");
  const [runs, setRuns] = useState<StrategyRun[]>([]);
  const [orders, setOrders] = useState<Record<string, unknown>[]>([]);
  const [status, setStatus] = useState("待运行");
  const [startDate, setStartDate] = useState("2026-01-01");
  const [endDate, setEndDate] = useState("2026-03-20");
  const [stockPool, setStockPool] = useState("000001,000002");
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [account, setAccount] = useState<AccountStatus | null>(null);

  const stockCodes = useMemo(
    () =>
      stockPool
        .split(/[,，\s]+/)
        .map((code) => code.trim())
        .filter(Boolean),
    [stockPool],
  );

  async function refresh() {
    const [nextRuns, nextOrders, nextAccount] = await Promise.all([listStrategyRuns(), listOrders(), getAccountStatus()]);
    setRuns(nextRuns);
    setOrders(nextOrders);
    setAccount(nextAccount);
  }

  async function handleReset() {
    setStatus("重置中");
    const newAccount = await resetAccount();
    setAccount(newAccount);
    await refresh();
    setStatus("已重置");
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
    const run = await runStrategy(strategyName, today);
    setRuns((current) => [run, ...current]);
    await refresh();
    setStatus("已提交");
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
    <section className="tool-layout">
      <div className="tool-main">
        <header className="section-header">
          <div>
            <h2>策略模拟</h2>
            <p>策略运行、假盘记录和日线级历史回测</p>
          </div>
          <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            <span className="status-pill">{status}</span>
            <button onClick={handleSync} type="button" title="从服务器同步全市场最新K线数据" className="secondary">
              <RefreshCw size={14} /> 同步历史数据
            </button>
          </div>
        </header>

        <div className="action-row" style={{ marginBottom: "20px", background: "var(--bg-card)", padding: "12px", borderRadius: "8px", border: "1px solid var(--border)", display: "flex", justifyContent: "space-between" }}>
          <div>
            <strong>初始资金：</strong> {account ? account.initial_balance.toLocaleString() : "..."} 元
            <strong style={{ marginLeft: "20px" }}>可用余额：</strong> <span style={{ color: "var(--text-accent)" }}>{account ? account.balance.toLocaleString() : "..."} 元</span>
          </div>
          <button onClick={handleReset} type="button" title="重置账户余额和订单记录" className="secondary">
            <RefreshCw size={14} /> 重置账户
          </button>
        </div>

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
            <form className="action-row" onSubmit={handleRun}>
              <StrategySelect value={strategyName} onChange={setStrategyName} />
              <button title="运行策略 (模拟盘实时运行)" type="submit">
                <Play size={17} />
                <span>运行</span>
              </button>
              <button title="刷新" type="button" onClick={() => refresh()}>
                <RefreshCw size={17} />
              </button>
            </form>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>策略</th>
                    <th>交易日</th>
                    <th>状态</th>
                    <th>任务</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.length === 0 ? (
                    <tr>
                      <td colSpan={4}>暂无策略运行记录。</td>
                    </tr>
                  ) : (
                    runs.map((run) => (
                      <tr key={run.id}>
                        <td>{run.display_name}</td>
                        <td>{run.trade_date}</td>
                        <td>{run.status}</td>
                        <td>{run.task_id.slice(0, 8)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
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

      <aside className="context-panel">
        <h3>{mode === "backtest" ? "回测概览" : "假盘订单"}</h3>
        {mode === "backtest" && backtestResult ? (
          <>
            <Metric label="交易数" value={backtestResult.trade_count} />
            <Metric label="总收益" value={`${backtestResult.total_return_pct}%`} />
            <Metric label="胜率" value={`${(backtestResult.win_rate * 100).toFixed(0)}%`} />
            <Metric label="最大回撤" value={`${backtestResult.max_drawdown_pct}%`} />
          </>
        ) : (
          <>
            <Metric label="订单数" value={orders.length} />
            <p>策略命中后将进入快照和本地假盘流程。</p>
          </>
        )}
      </aside>
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

function Metric({ label, value }: { label: string; value: number | string }) {
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
