import { FormEvent, useEffect, useState } from "react";
import { Play, RefreshCw } from "lucide-react";
import { StrategyRun, listOrders, listStrategyRuns, runStrategy } from "../api/client";

export function StrategySimulationPage() {
  const [tradeDate, setTradeDate] = useState("2026-04-27");
  const [strategyName, setStrategyName] = useState("trend_reversal");
  const [runs, setRuns] = useState<StrategyRun[]>([]);
  const [orders, setOrders] = useState<Record<string, unknown>[]>([]);
  const [status, setStatus] = useState("待运行");

  async function refresh() {
    const [nextRuns, nextOrders] = await Promise.all([listStrategyRuns(), listOrders()]);
    setRuns(nextRuns);
    setOrders(nextOrders);
  }

  async function handleRun(event: FormEvent) {
    event.preventDefault();
    setStatus("排队中");
    const run = await runStrategy(strategyName, tradeDate);
    setRuns((current) => [run, ...current]);
    setStatus("已提交");
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
            <p>均线放量突破</p>
          </div>
          <span className="status-pill">{status}</span>
        </header>

        <form className="action-row" onSubmit={handleRun}>
          <label>
            策略
            <select value={strategyName} onChange={(event) => setStrategyName(event.target.value)}>
              <option value="trend_reversal">趋势反转策略</option>
              <option value="moving_average_breakout">均线放量突破</option>
            </select>
          </label>
          <label>
            交易日
            <input
              value={tradeDate}
              onChange={(event) => setTradeDate(event.target.value)}
              type="date"
            />
          </label>
          <button title="运行策略" type="submit">
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
      </div>

      <aside className="context-panel">
        <h3>假盘订单</h3>
        <div className="metric">
          <span>订单数</span>
          <strong>{orders.length}</strong>
        </div>
        <p>策略命中后将进入快照和本地假盘流程。</p>
      </aside>
    </section>
  );
}
