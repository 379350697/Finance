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
