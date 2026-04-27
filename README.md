# A Share Strategy Assistant

A lightweight A-share strategy assistant with an extensible backend frame. The first version is designed to close the loop from data retrieval to strategy screening, snapshots, paper trading, LLM reports, and single-agent stock Q&A.

## Architecture

- `backend`: FastAPI app, SQLAlchemy models, Alembic migrations, Celery worker tasks.
- `frontend`: React + Vite + TypeScript tool UI.
- `postgres`: persistent business data.
- `redis`: Celery broker and task backend.
- `data`: normalized market-data service, defaulting to AKShare.
- `strategy`: registry-based strategy modules; adding a strategy should feel like adding a component.
- `llm`: `openai_codex` provider abstraction with deterministic fallback reports.
- `ask_stock`: single Agent Q&A backed by tool context.

## Environment

Copy `.env.example` to `.env` and fill optional keys:

```bash
FINANCE_DATABASE_URL=postgresql+psycopg://finance:finance@postgres:5432/finance
FINANCE_REDIS_URL=redis://redis:6379/0
FINANCE_LLM_PROVIDER=openai_codex
FINANCE_LLM_API_KEY=
FINANCE_LLM_BASE_URL=
FINANCE_LLM_MODEL=openai-codex
FINANCE_TUSHARE_TOKEN=
```

If the LLM settings are empty, reports and ask-stock responses still return local fallback content.

## Local Runtime

Start the stack:

```bash
docker compose up --build
```

Open:

- Backend health: `http://localhost:8000/health`
- Frontend app: `http://localhost:5173`

## Backend Commands

Run tests:

```bash
cd backend
python -m pytest -v
```

Run API locally:

```bash
cd backend
uvicorn app.main:app --reload
```

Run worker locally:

```bash
cd backend
celery -A app.worker.celery_app.celery_app worker --loglevel=INFO
```

## Frontend Commands

Install and run:

```bash
cd frontend
npm install
npm run dev
```

Run tests:

```bash
npm test -- --run
```

## First Workflow

1. Start the stack.
2. Open the frontend.
3. Run `策略模拟` for `moving_average_breakout`.
4. Generate an `LLM 分析` daily report.
5. Ask `分析一下 000001` in `问股`.

## Closed Loop Demo

The backend includes a deterministic demo that does not call live market APIs:

```bash
cd backend
python -m pytest tests/test_closed_loop.py -v
```

It runs:

1. Generate sample bars for `000001`.
2. Evaluate the `moving_average_breakout` strategy.
3. Build a stock snapshot.
4. Create a paper order.
5. Settle by close price.
6. Generate a fallback daily report.

## Strategy Extension

Add a new strategy under `backend/app/services/strategy/`, implement the base evaluate shape, and register it in `registry.py`. The common flow will continue to handle candidates, snapshots, paper orders, settlement, and LLM reports.

## Backtest Module

The first backtest module is intentionally lightweight:

- API: `POST /api/backtests/run`
- Inputs: `strategy_name`, `start_date`, `end_date`, `stock_pool`, and per-stock daily bars.
- Engine: evaluates the selected strategy once per daily bar.
- Execution rule: buy at the signal day's close and exit after `holding_days` trading days, defaulting to the next close.
- Outputs: trade details, daily returns, total return, win rate, and max drawdown.
- Frontend: the Strategy Simulation page includes a `Backtest` tab.

## Built-In Strategies

- `moving_average_breakout`: 5 日均线放量突破。
- `trend_reversal`: 趋势反转策略。规则为收益预增、今天前至少日线三连阴、盘中上涨且放量，或有 500 万以上大单流入，同时 60 日均线处于上升趋势。
