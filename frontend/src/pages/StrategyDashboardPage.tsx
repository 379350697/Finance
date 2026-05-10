import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { usePolling } from "../hooks/usePolling";
import {
  PaperStats,
  PaperOrder,
  NetValuePoint,
  StrategyRun,
  getPaperStats,
  getNetValue,
  listOrders,
  listStrategyRuns,
} from "../api/client";

const strategies = [
  { value: "trend_reversal", label: "趋势反转策略" },
  { value: "moving_average_breakout", label: "均线放量突破" },
  { value: "test_fast_execution", label: "快速测试闭环" },
] as const;

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

interface Props {
  onStrategyClick: (strategyName: string) => void;
}

export function StrategyDashboardPage({ onStrategyClick }: Props) {
  const [isInitialLoading, setIsInitialLoading] = useState(true);

  const liveStats = usePolling(
    () => getPaperStats().catch(() => defaultStats),
    10000,
  );
  const liveChart = usePolling(
    () => getNetValue().catch(() => [] as NetValuePoint[]),
    30000,
  );
  const liveOrders = usePolling(
    () => listOrders().catch(() => [] as PaperOrder[]),
    10000,
  );
  const liveRuns = usePolling(
    () => listStrategyRuns().catch(() => [] as StrategyRun[]),
    10000,
  );

  const [stats, setStats] = useState<PaperStats>(defaultStats);
  const [chartData, setChartData] = useState<NetValuePoint[]>([]);
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [runs, setRuns] = useState<StrategyRun[]>([]);

  useEffect(() => { if (liveStats) setStats(liveStats); }, [liveStats]);
  useEffect(() => { if (liveChart) setChartData(liveChart); }, [liveChart]);
  useEffect(() => { if (liveOrders) setOrders(liveOrders); }, [liveOrders]);
  useEffect(() => { if (liveRuns) setRuns(liveRuns); }, [liveRuns]);

  useEffect(() => {
    Promise.all([
      getPaperStats().catch(() => defaultStats),
      getNetValue().catch(() => [] as NetValuePoint[]),
      listOrders().catch(() => [] as PaperOrder[]),
      listStrategyRuns().catch(() => [] as StrategyRun[]),
    ]).then(([s, c, o, r]) => {
      setStats(s);
      setChartData(c);
      setOrders(o);
      setRuns(r);
      setIsInitialLoading(false);
    });
  }, []);

  const activeStrategies = useMemo(() => {
    const activeNames = new Set(runs.filter((r) => r.status === "running").map((r) => r.strategy_name));
    return activeNames.size;
  }, [runs]);

  const statusText = useMemo(() => {
    if (isInitialLoading) return "加载中…";
    if (activeStrategies > 0) return `${activeStrategies} 策略运行中`;
    return "待运行";
  }, [activeStrategies, isInitialLoading]);

  const recentOrders = useMemo(() => orders.slice(0, 8), [orders]);

  const strategyCards = useMemo(() => {
    return strategies.map((s) => {
      const strategyRuns = runs.filter((r) => r.strategy_name === s.value);
      const strategyOrders = orders.filter((o) => o.strategy_name === s.value);
      const totalPnl = strategyOrders.reduce((sum, o) => sum + (o.pnl || 0), 0);
      const closedOrders = strategyOrders.filter((o) => o.status === "settled" || o.close_price != null);
      const winCount = closedOrders.filter((o) => (o.pnl || 0) > 0).length;
      const winRate = closedOrders.length > 0 ? ((winCount / closedOrders.length) * 100).toFixed(1) + "%" : "--";
      const isRunning = strategyRuns.some((r) => r.status === "running");
      const lastRun = strategyRuns.length > 0 ? strategyRuns[0].trade_date : null;
      const lastMatched = strategyRuns.length > 0 ? strategyRuns[0].matched_count : null;

      return { ...s, totalPnl, tradeCount: closedOrders.length, winRate, isRunning, lastRun, lastMatched };
    });
  }, [runs, orders]);

  const formatPnl = (val: number) => {
    const sign = val >= 0 ? "+" : "";
    return `${sign}${val.toLocaleString()}`;
  };

  if (isInitialLoading) {
    return (
      <section>
        <div className="section-header page-enter">
          <div className="skeleton" style={{ width: 180, height: 32 }} />
        </div>
        <div className="account-bar page-enter">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton" style={{ width: 120, height: 48, borderRadius: "var(--radius-md)" }} />
          ))}
        </div>
        <div className="metric-grid page-enter">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton" style={{ height: 72 }} />
          ))}
        </div>
        <div style={{ display: "grid", gap: "var(--space-md)", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))" }} className="page-enter">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton" style={{ height: 200 }} />
          ))}
        </div>
      </section>
    );
  }

  return (
    <section>
      {/* Section Header */}
      <div className="section-header page-enter">
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-md)" }}>
          <h2>策略仪表盘</h2>
          <span className={`status-pill${activeStrategies > 0 ? "" : " status-pill--idle"}`}>
            {statusText}
          </span>
        </div>
        <span className="last-updated">
          {stats.total_assets !== defaultStats.total_assets ? "实时数据" : "暂无数据"}
        </span>
      </div>

      {/* Account Bar */}
      <div className="account-bar page-enter">
        <div style={{ textAlign: "center", flex: 1 }}>
          <strong>总资产</strong>
          <div className="account-value">
            ¥{(stats.total_assets ?? 0).toLocaleString()}
          </div>
        </div>
        <div style={{ width: 1, height: 40, background: "var(--border-subtle)" }} />
        <div style={{ textAlign: "center", flex: 1 }}>
          <strong>累计盈亏</strong>
          <div
            className={`account-value${(stats.cumulative_pnl ?? 0) >= 0 ? " account-value--accent" : ""}`}
            style={stats.cumulative_pnl < 0 ? { color: "var(--color-down)" } : undefined}
          >
            {formatPnl(stats.cumulative_pnl ?? 0)}
          </div>
        </div>
        <div style={{ width: 1, height: 40, background: "var(--border-subtle)" }} />
        <div style={{ textAlign: "center", flex: 1 }}>
          <strong>可用余额</strong>
          <div className="account-value">
            ¥{(stats.balance ?? 0).toLocaleString()}
          </div>
        </div>
        <div style={{ width: 1, height: 40, background: "var(--border-subtle)" }} />
        <div style={{ textAlign: "center", flex: 1 }}>
          <strong>持仓市值</strong>
          <div className="account-value">
            ¥{(stats.positions_market_value ?? 0).toLocaleString()}
          </div>
        </div>
      </div>

      {/* KPI Row */}
      <div className="metric-grid page-enter">
        <div className="metric">
          <strong style={{ color: (stats.annualized_return ?? 0) >= 0 ? "var(--color-up)" : "var(--color-down)" }}>
            {(stats.annualized_return ?? 0) >= 0 ? "+" : ""}
            {(stats.annualized_return ?? 0).toFixed(1)}%
          </strong>
          <span>年化收益率</span>
        </div>
        <div className="metric">
          <strong style={{ color: "var(--color-down)" }}>
            {(stats.max_drawdown ?? 0).toFixed(1)}%
          </strong>
          <span>最大回撤</span>
        </div>
        <div className="metric">
          <strong>{(stats.win_rate ?? 0).toFixed(1)}%</strong>
          <span>策略胜率</span>
        </div>
        <div className="metric">
          <strong>{stats.total_trades ?? 0}</strong>
          <span>总交易数</span>
        </div>
      </div>

      {/* Strategy Cards */}
      <div style={{ marginBottom: "var(--space-lg)" }} className="page-enter">
        <h3 style={{ fontFamily: "var(--font-display)", fontSize: "var(--font-size-lg)", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "var(--space-md)" }}>
          策略总览
        </h3>
        <div style={{ display: "grid", gap: "var(--space-md)", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))" }}>
          {strategyCards.map((card) => (
            <div
              key={card.value}
              className="metric"
              onClick={() => onStrategyClick(card.value)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onStrategyClick(card.value); }}
              role="button"
              tabIndex={0}
              style={{
                padding: "var(--space-md)",
                flexDirection: "column",
                alignItems: "stretch",
                gap: "var(--space-sm)",
                cursor: "pointer",
              }}
            >
              {/* Card Header */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <h4 style={{ fontFamily: "var(--font-display)", fontSize: "var(--font-size-lg)", fontWeight: 600, margin: 0 }}>
                  {card.label}
                </h4>
                <span className={`status-pill${card.isRunning ? "" : " status-pill--idle"}`}>
                  {card.isRunning ? "运行中" : "待运行"}
                </span>
              </div>

              {/* Sparkline */}
              <div style={{ width: "100%", height: 80 }}>
                {chartData.length > 1 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id={`spark-${card.value}`} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="var(--color-up)" stopOpacity={0.2} />
                          <stop offset="95%" stopColor="var(--color-up)" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <Area type="monotone" dataKey="value" stroke="var(--color-up)" strokeWidth={1.5} fill={`url(#spark-${card.value})`} />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-tertiary)", fontSize: "var(--font-size-xs)" }}>
                    暂无净值数据
                  </div>
                )}
              </div>

              {/* Card Stats */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--space-xs)", textAlign: "center" }}>
                <div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--font-size-lg)", fontWeight: 700, color: card.totalPnl >= 0 ? "var(--color-up)" : "var(--color-down)" }}>
                    {formatPnl(card.totalPnl)}
                  </div>
                  <div style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase" }}>累计盈亏</div>
                </div>
                <div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--font-size-lg)", fontWeight: 700 }}>{card.winRate}</div>
                  <div style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase" }}>胜率</div>
                </div>
                <div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--font-size-lg)", fontWeight: 700 }}>{card.tradeCount}</div>
                  <div style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase" }}>交易数</div>
                </div>
              </div>

              {/* Card Footer */}
              <div style={{ display: "flex", justifyContent: "space-between", paddingTop: "var(--space-xs)", borderTop: "1px solid var(--border-subtle)" }}>
                <span style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-mono)", fontSize: 10 }}>
                  上次运行: {card.lastRun ?? "--"}
                </span>
                <span style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-mono)", fontSize: 10 }}>
                  匹配: {card.lastMatched != null ? `${card.lastMatched} 只` : "--"}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Orders */}
      <div className="table-wrap page-enter">
        <h3 style={{ fontFamily: "var(--font-display)", fontSize: "var(--font-size-lg)", fontWeight: 600, padding: "var(--space-md) var(--space-md) 0", color: "var(--text-secondary)" }}>
          最近订单
        </h3>
        {recentOrders.length === 0 ? (
          <div className="empty-state">
            <span>暂无订单</span>
            <span className="empty-state-hint">运行策略后将在此显示订单记录</span>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>股票</th>
                <th>方向</th>
                <th>价格</th>
                <th>数量</th>
                <th>盈亏</th>
                <th>策略</th>
              </tr>
            </thead>
            <tbody>
              {recentOrders.map((order) => {
                const strategyLabel = strategies.find((s) => s.value === order.strategy_name)?.label ?? order.strategy_name;
                const pnlClass = (order.pnl ?? 0) > 0 ? "var(--color-up)" : (order.pnl ?? 0) < 0 ? "var(--color-down)" : "var(--text-primary)";
                const sideClass = order.side === "buy" ? "var(--color-up)" : "var(--color-down)";
                const sideLabel = order.side === "buy" ? "买入" : "卖出";
                return (
                  <tr key={order.id}>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: "var(--font-size-xs)", color: "var(--text-secondary)" }}>
                      {order.created_at ? new Date(order.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) : "--"}
                    </td>
                    <td>
                      {order.stock_code}
                      {order.stock_name ? ` ${order.stock_name}` : ""}
                    </td>
                    <td>
                      <span
                        style={{
                          display: "inline-block",
                          borderRadius: "var(--radius-sm)",
                          padding: "1px 6px",
                          fontFamily: "var(--font-mono)",
                          fontSize: 10,
                          fontWeight: 700,
                          background: order.side === "buy" ? "var(--color-up-bg)" : "var(--color-down-bg)",
                          color: sideClass,
                        }}
                      >
                        {sideLabel}
                      </span>
                    </td>
                    <td>{order.entry_price?.toFixed(2) ?? "--"}</td>
                    <td>{order.quantity ?? "--"}</td>
                    <td style={{ color: pnlClass, fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                      {order.pnl != null ? `${order.pnl >= 0 ? "+" : ""}${order.pnl.toLocaleString()}` : "--"}
                    </td>
                    <td style={{ color: "var(--text-tertiary)", fontSize: "var(--font-size-xs)" }}>
                      {strategyLabel}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
