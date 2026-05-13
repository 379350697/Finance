const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://115.191.10.107:8000";

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
  matched_count: number;
  error_message?: string;
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
  // Enhanced fields (available when enable_ic_analysis is true)
  annualized_return?: number;
  sharpe_ratio?: number;
  information_ratio?: number;
  max_drawdown_duration?: number;
  turnover_rate?: number;
  hit_rate?: number;
  ic_summary?: ICAnalysisSummary | null;
  attribution?: AttributionResult | null;
};

// ── Factor & Model types ─────────────────────────────────────────────────

export type FactorComputeRequest = {
  codes: string[];
  start_date: string;
  end_date: string;
  factor_set: string;
};

export type FactorComputeResponse = {
  codes_count: number;
  factor_count: number;
  date_range: [string, string];
  factor_names: string[];
  status: string;
};

export type ModelTrainRequest = {
  model_name: string;
  factor_set: string;
  train_start: string;
  train_end: string;
  valid_start: string;
  valid_end: string;
  test_start: string;
  test_end: string;
  stock_pool: string[];
  model_type: string;
  label_type: string;
  hyperparams: Record<string, number | string | boolean>;
};

export type ModelTrainResult = {
  model_name: string;
  model_type: string;
  factor_set: string;
  ic_mean: number;
  ic_std: number;
  icir: number;
  rank_ic_mean: number;
  rank_ic_std: number;
  rank_icir: number;
  mse: number;
  mae: number;
  feature_importance: Record<string, number>;
  status: string;
};

export type ModelPredictRequest = {
  model_name: string;
  codes: string[];
  predict_date: string;
  model_type?: string;
};

export type StockScore = {
  code: string;
  score: number;
  rank: number;
};

export type ModelPredictResponse = {
  predictions: StockScore[];
};

export type ICPoint = {
  date: string;
  ic: number;
  rank_ic: number;
};

export type ICAnalysisSummary = {
  ic_mean: number;
  ic_std: number;
  icir: number;
  rank_ic_mean: number;
  rank_ic_std: number;
  rank_icir: number;
  ic_series: ICPoint[];
};

export type FactorICData = {
  factor_name: string;
  ic_mean: number;
  ic_std: number;
  icir: number;
};

// ── Model Comparison ────────────────────────────────────────────────────

export type ModelCompareItem = {
  model_type: string;
  ic_mean: number;
  ic_std: number;
  icir: number;
  rank_ic_mean: number;
  rank_icir: number;
  mse: number;
  mae: number;
  train_time_seconds: number;
  status: string;
};

export type ModelCompareRequest = {
  model_name_prefix: string;
  factor_set: string;
  train_start: string;
  train_end: string;
  valid_start: string;
  valid_end: string;
  test_start: string;
  test_end: string;
  stock_pool: string[];
  label_type: string;
  model_types: string[];
  hyperparams: Record<string, number | string | boolean>;
};

export type ModelCompareResponse = {
  comparison: ModelCompareItem[];
  best_model: string;
};

// ── Rolling Retraining ──────────────────────────────────────────────────

export type RollingTrainRequest = {
  base_model_name: string;
  model_type: string;
  factor_set: string;
  stock_pool: string[];
  label_type: string;
  window_days: number;
  step_days: number;
  min_train_days: number;
  start_date: string | null;
  end_date: string | null;
  hyperparams: Record<string, number | string | boolean>;
};

export type WindowResult = {
  window_index: number;
  train_start: string;
  train_end: string;
  valid_start: string;
  valid_end: string;
  test_start: string;
  test_end: string;
  ic_mean: number;
  icir: number;
  rank_ic_mean: number;
  rank_icir: number;
  model_path: string;
};

export type RollingTrainResponse = {
  windows: WindowResult[];
  ic_decay_trend: number;
  model_type: string;
  factor_set: string;
  total_windows: number;
};

// ── Portfolio Optimization ───────────────────────────────────────────────

export type PortfolioOptRequest = {
  codes: string[];
  start_date: string;
  end_date: string;
  method: string;
  constraints: Record<string, number>;
  scores: Record<string, number> | null;
};

export type FrontierPoint = {
  volatility: number;
  expected_return: number;
  sharpe_ratio: number;
  weights: number[];
};

export type PortfolioOptResult = {
  weights: Record<string, number>;
  expected_return: number;
  expected_volatility: number;
  sharpe_ratio: number;
  efficient_frontier: FrontierPoint[];
};

// ── Attribution ──────────────────────────────────────────────────────────

export type AttributionEffect = {
  name: string;
  value: number;
  pct: number;
};

export type BrinsonResult = {
  allocation_effects: AttributionEffect[];
  selection_effects: AttributionEffect[];
  interaction_effects: AttributionEffect[];
  total_excess: number;
};

export type FactorAttributionResult = {
  factor_contributions: AttributionEffect[];
  residual: AttributionEffect | null;
  total_return: number;
};

export type AttributionResult = {
  brinson: BrinsonResult | null;
  factor: FactorAttributionResult | null;
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
  use_exchange_sim?: boolean;
  use_execution_sim?: boolean;
  enable_ic_analysis?: boolean;
  enable_attribution?: boolean;
  portfolio_method?: string;
  portfolio_constraints?: Record<string, number>;
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

export function pauseStrategyRun(runId: string) {
  return request<{ id: string; status: string }>(`/api/strategies/runs/${runId}/pause`, {
    method: "POST",
  });
}

export function resumeStrategyRun(runId: string) {
  return request<{ id: string; status: string }>(`/api/strategies/runs/${runId}/resume`, {
    method: "POST",
  });
}

export function terminateStrategyRun(runId: string) {
  return request<{ id: string; status: string }>(`/api/strategies/runs/${runId}/terminate`, {
    method: "POST",
  });
}

export function runBacktest(payload: BacktestRequest) {
  return request<BacktestResult>("/api/backtests/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listOrders() {
  return request<PaperOrder[]>("/api/paper-trading/orders");
}

export type PaperOrder = {
  id: string;
  stock_code: string;
  stock_name: string;
  strategy_name: string;
  trade_date: string;
  side: string;
  entry_price: number;
  close_price: number | null;
  quantity: number;
  pnl: number;
  return_pct: number;
  status: string;
  run_id: string;
  created_at: string | null;
  settled_at: string | null;
};

export type AccountStatus = {
  balance: number;
  initial_balance: number;
};

export type PaperPosition = {
  id: string;
  stock_code: string;
  stock_name: string;
  quantity: number;
  average_price: number;
  market_value: number;
  pnl: number;
  return_pct: number;
  status: string;
  opened_at: string | null;
};

export type PaperStats = {
  total_assets: number;
  balance: number;
  initial_balance: number;
  cumulative_pnl: number;
  cumulative_pnl_pct: number;
  annualized_return: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  open_orders: number;
  positions_market_value: number;
};

export type NetValuePoint = {
  date: string;
  value: number;
  pnl: number;
};

export function getAccountStatus() {
  return request<AccountStatus>("/api/paper-trading/account");
}

export function resetAccount() {
  return request<AccountStatus>("/api/paper-trading/account/reset", {
    method: "POST",
  });
}

export function listPositions() {
  return request<PaperPosition[]>("/api/paper-trading/positions");
}

export function getPaperStats() {
  return request<PaperStats>("/api/paper-trading/stats");
}

export function getNetValue() {
  return request<NetValuePoint[]>("/api/paper-trading/net-value");
}

export function settlePaperTrading(tradeDate: string) {
  return request<{ trade_date: string; settled_count: number; status: string }>(
    `/api/paper-trading/settle?trade_date=${tradeDate}`,
    { method: "POST" },
  );
}

export function getSyncStatus() {
  return request<{ cached_count: number }>("/api/data/status");
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

// ── OAuth ────────────────────────────────────────────────────────────────

export type OAuthStatus = {
  authenticated: boolean;
  expires_at?: number;
  has_refresh_token?: boolean;
};

export type OAuthStartResult = {
  authorize_url: string;
  state: string;
};

export type DeviceAuthStartResult = {
  device_auth_id: string;
  user_code: string;
  verification_url: string;
  interval: number;
};

export function getOAuthStatus() {
  return request<OAuthStatus>("/api/llm/oauth/status");
}

export function startOAuth() {
  return request<OAuthStartResult>("/api/llm/oauth/start", { method: "POST" });
}

export function postOAuthCallback(code: string, state: string) {
  return request<{ status: string }>("/api/llm/oauth/callback", {
    method: "POST",
    body: JSON.stringify({ code, state }),
  });
}

export function logoutOAuth() {
  return request<{ status: string }>("/api/llm/oauth/logout", { method: "POST" });
}

export function startDeviceAuth() {
  return request<DeviceAuthStartResult>("/api/llm/oauth/device/start", { method: "POST" });
}

export function pollDeviceAuth(deviceAuthId: string, userCode: string) {
  return request<{ status: string }>("/api/llm/oauth/device/poll", {
    method: "POST",
    body: JSON.stringify({ device_auth_id: deviceAuthId, user_code: userCode }),
  });
}

export type MinuteBar = {
  code: string;
  trade_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
  turnover?: number;
};

export type MarketBarsResponse = {
  code: string;
  period: string;
  bars: MinuteBar[];
};

export function getMarketBars(code: string, period = "5", start = "", end = "") {
  const params = new URLSearchParams({ period });
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  return request<MarketBarsResponse>(`/api/market/bars/${code}?${params}`);
}

export function getMarketQuote(code: string) {
  return request<{ code: string; name: string; price: number; change_pct?: number; volume?: number; turnover?: number }>(
    `/api/market/quote/${code}`,
  );
}

export function syncMarketData() {
  return request<{ status: string }>("/api/data/sync", {
    method: "POST",
  });
}

// ── Factor & Model API ───────────────────────────────────────────────────

export function computeFactors(req: FactorComputeRequest) {
  return request<FactorComputeResponse>("/api/factors/compute", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function getFactorICSummary(
  factorSet: string,
  codes: string[],
  startDate: string,
  endDate: string,
) {
  return request<ICAnalysisSummary & { factor_ic: FactorICData[] }>(
    "/api/factors/ic-analysis",
    {
      method: "POST",
      body: JSON.stringify({
        factor_set: factorSet,
        codes,
        start_date: startDate,
        end_date: endDate,
      }),
    },
  );
}

export function trainModel(req: ModelTrainRequest) {
  return request<ModelTrainResult>("/api/models/train", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function predictModel(req: ModelPredictRequest) {
  return request<ModelPredictResponse>("/api/models/predict", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function listModels() {
  return request<ModelTrainResult[]>("/api/models");
}

export function getModel(name: string) {
  return request<ModelTrainResult>(`/api/models/${encodeURIComponent(name)}`);
}

export function compareModels(req: ModelCompareRequest) {
  return request<ModelCompareResponse>("/api/models/compare", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function rollingTrain(req: RollingTrainRequest) {
  return request<RollingTrainResponse>("/api/models/rolling-train", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function optimizePortfolio(req: PortfolioOptRequest) {
  return request<PortfolioOptResult>("/api/backtests/optimize", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
