const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export type AskSession = {
  id: string;
  title: string;
};

export type AskMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

export type StrategyRun = {
  id: string;
  task_id: string;
  strategy_name: string;
  display_name: string;
  trade_date: string;
  status: string;
};

export type DailyBar = {
  code: string;
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
  turnover?: number;
};

export type BacktestTrade = {
  stock_code: string;
  stock_name?: string;
  strategy_name: string;
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  pnl: number;
  return_pct: number;
  signal_score: number;
  signal_reason: string;
  metrics: Record<string, unknown>;
};

export type BacktestDailyReturn = {
  trade_date: string;
  pnl: number;
  return_pct: number;
  cumulative_return_pct: number;
  trades: number;
};

export type BacktestResult = {
  strategy_name: string;
  start_date: string;
  end_date: string;
  stock_pool: string[];
  initial_capital: number;
  position_size: number;
  trade_count: number;
  win_rate: number;
  total_return_pct: number;
  max_drawdown_pct: number;
  trades: BacktestTrade[];
  daily_returns: BacktestDailyReturn[];
};

export type BacktestRequest = {
  strategy_name: string;
  start_date: string;
  end_date: string;
  stock_pool: string[];
  initial_capital?: number;
  position_size?: number;
  holding_days?: number;
  strategy_params?: Record<string, unknown>;
  stocks: Array<{
    code: string;
    name?: string;
    bars: DailyBar[];
    context?: Record<string, unknown>;
  }>;
};

export type Report = {
  id: string;
  period_type: string;
  period_start: string;
  period_end: string;
  title: string;
  content: string;
  provider: string;
  status: string;
};

export function createAskSession(title: string) {
  return request<AskSession>("/api/ask-stock/sessions", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export function sendAskMessage(sessionId: string, content: string) {
  return request<{ session_id: string; messages: AskMessage[] }>(
    `/api/ask-stock/sessions/${sessionId}/messages`,
    {
      method: "POST",
      body: JSON.stringify({ content }),
    },
  );
}

export function runStrategy(strategyName: string, tradeDate: string) {
  return request<StrategyRun>("/api/strategies/run", {
    method: "POST",
    body: JSON.stringify({ strategy_name: strategyName, trade_date: tradeDate }),
  });
}

export function listStrategyRuns() {
  return request<StrategyRun[]>("/api/strategies/runs");
}

export function runBacktest(payload: BacktestRequest) {
  return request<BacktestResult>("/api/backtests/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listOrders() {
  return request<Record<string, unknown>[]>("/api/paper-trading/orders");
}

export function generateReport(periodType: string, periodStart: string, periodEnd: string) {
  return request<Report>("/api/reports/generate", {
    method: "POST",
    body: JSON.stringify({
      period_type: periodType,
      period_start: periodStart,
      period_end: periodEnd,
      candidates_count: 0,
      orders_count: 0,
      total_return_pct: 0,
    }),
  });
}

export function listReports() {
  return request<Report[]>("/api/reports");
}
