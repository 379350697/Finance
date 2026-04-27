# A Share Strategy Assistant Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a lightweight but extensible A-share strategy assistant with data ingestion, strategy simulation, paper trading, LLM reports, and single-agent stock Q&A.

**Architecture:** Use one FastAPI backend codebase with clear internal modules, backed by PostgreSQL, Redis, and Celery. The first version implements a simple closed loop while keeping the heavier production framework ready for future expansion.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis, Celery, AKShare, optional Tushare, React, Vite, TypeScript, Vitest, Docker Compose.

---

## Implementation Notes

- Keep the backend as one app under `backend/app`.
- Keep all long-running jobs behind Celery tasks, even if the first version calls small functions.
- Use mock data in tests so CI does not depend on live A-share APIs.
- Start with one built-in strategy and one deterministic paper-trading rule.
- Keep the LLM provider interface pluggable. The default provider name is `openai_codex`; API key, base URL, and model are configured by environment variables. If the OpenAI Codex configuration is missing, return a deterministic fallback report so the UI still closes the loop.
- Do not implement multi-agent Q&A.

## Task 1: Repository Skeleton

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/test_health.py`
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles.css`

**Step 1: Create minimal backend health test**

```python
# backend/tests/test_health.py
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Step 2: Add minimal FastAPI app**

```python
# backend/app/main.py
from fastapi import FastAPI

app = FastAPI(title="A Share Strategy Assistant")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

**Step 3: Add backend package metadata**

```toml
# backend/pyproject.toml
[project]
name = "a-share-strategy-assistant"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "sqlalchemy>=2.0.0",
  "alembic>=1.13.0",
  "psycopg[binary]>=3.2.0",
  "pydantic-settings>=2.4.0",
  "redis>=5.0.0",
  "celery>=5.4.0",
  "akshare>=1.15.0",
  "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0.0",
  "pytest-asyncio>=0.23.0",
  "ruff>=0.6.0",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

**Step 4: Add minimal frontend**

```tsx
// frontend/src/App.tsx
export function App() {
  return (
    <main className="app-shell">
      <aside className="sidebar">
        <h1>A 股策略助手</h1>
        <nav>
          <button>问股</button>
          <button>策略模拟</button>
          <button>LLM 分析</button>
        </nav>
      </aside>
      <section className="workspace">
        <h2>策略模拟</h2>
        <p>项目骨架已启动。</p>
      </section>
    </main>
  );
}
```

**Step 5: Run verification**

Run:

```bash
cd backend
python -m pytest tests/test_health.py -v
```

Expected: `1 passed`.

**Step 6: Commit**

```bash
git add .gitignore README.md docker-compose.yml .env.example backend frontend
git commit -m "chore: scaffold project"
```

## Task 2: Configuration, Database, and Celery Base

**Files:**
- Create: `backend/app/core/config.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/worker/celery_app.py`
- Create: `backend/app/api/router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_config.py`

**Step 1: Write config test**

```python
# backend/tests/test_config.py
from app.core.config import Settings


def test_settings_defaults_are_local_dev_friendly():
    settings = Settings()

    assert settings.app_name == "A Share Strategy Assistant"
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.redis_url.startswith("redis://")
```

**Step 2: Implement settings**

```python
# backend/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "A Share Strategy Assistant"
    database_url: str = "postgresql+psycopg://finance:finance@localhost:5432/finance"
    redis_url: str = "redis://localhost:6379/0"
    llm_provider: str = "openai_codex"
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str = "openai-codex"
    tushare_token: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_prefix="FINANCE_")


settings = Settings()
```

**Step 3: Implement DB session**

```python
# backend/app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Step 4: Implement Celery app**

```python
# backend/app/worker/celery_app.py
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "finance_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"],
)
```

**Step 5: Wire API router**

```python
# backend/app/api/router.py
from fastapi import APIRouter

router = APIRouter()
```

Update `backend/app/main.py` to include `router` under `/api`.

**Step 6: Run verification**

Run:

```bash
cd backend
python -m pytest tests/test_config.py tests/test_health.py -v
```

Expected: all tests pass.

**Step 7: Commit**

```bash
git add backend/app/core backend/app/db backend/app/worker backend/app/api backend/app/main.py backend/tests
git commit -m "chore: add backend runtime foundations"
```

## Task 3: Domain Models and Alembic

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_initial_schema.py`
- Create: `backend/app/models/stock.py`
- Create: `backend/app/models/strategy.py`
- Create: `backend/app/models/snapshot.py`
- Create: `backend/app/models/paper_trading.py`
- Create: `backend/app/models/report.py`
- Create: `backend/app/models/ask.py`
- Create: `backend/app/models/task_run.py`
- Modify: `backend/app/db/base.py`
- Test: `backend/tests/test_models.py`

**Step 1: Write metadata test**

```python
# backend/tests/test_models.py
from app.db.base import Base


def test_expected_tables_are_registered():
    expected = {
        "stocks",
        "strategy_runs",
        "strategy_candidates",
        "stock_snapshots",
        "paper_orders",
        "paper_positions",
        "paper_daily_returns",
        "llm_reports",
        "ask_sessions",
        "ask_messages",
        "task_runs",
    }

    assert expected.issubset(set(Base.metadata.tables))
```

**Step 2: Implement model base and imports**

```python
# backend/app/db/base.py
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.ask import AskMessage, AskSession  # noqa: E402,F401
from app.models.paper_trading import PaperDailyReturn, PaperOrder, PaperPosition  # noqa: E402,F401
from app.models.report import LlmReport  # noqa: E402,F401
from app.models.snapshot import StockSnapshot  # noqa: E402,F401
from app.models.stock import Stock  # noqa: E402,F401
from app.models.strategy import StrategyCandidate, StrategyRun  # noqa: E402,F401
from app.models.task_run import TaskRun  # noqa: E402,F401
```

**Step 3: Implement SQLAlchemy models**

Use SQLAlchemy 2.0 `Mapped` and `mapped_column`. Store flexible market snapshot and LLM inputs in `JSON` columns. Keep primary keys as UUID strings or integer IDs consistently; prefer UUID strings for run/session/report records.

**Step 4: Add Alembic initial migration**

Create all tables listed in the design doc. Include indexes on:

- `stocks.code`
- `strategy_runs.trade_date`
- `strategy_candidates.run_id`
- `stock_snapshots.trade_date`
- `stock_snapshots.stock_code`
- `paper_orders.trade_date`
- `llm_reports.period_type`
- `ask_messages.session_id`

**Step 5: Run verification**

Run:

```bash
cd backend
python -m pytest tests/test_models.py -v
```

Expected: test passes.

**Step 6: Commit**

```bash
git add backend/alembic.ini backend/alembic backend/app/models backend/app/db/base.py backend/tests/test_models.py
git commit -m "feat: add core database schema"
```

## Task 4: Market Data Provider

**Files:**
- Create: `backend/app/schemas/market.py`
- Create: `backend/app/services/data/provider.py`
- Create: `backend/app/services/data/akshare_provider.py`
- Create: `backend/app/services/data/service.py`
- Test: `backend/tests/services/test_market_data_service.py`

**Step 1: Write provider fallback test**

```python
# backend/tests/services/test_market_data_service.py
from datetime import date

from app.schemas.market import StockQuote
from app.services.data.service import MarketDataService


class FakeProvider:
    def get_quote(self, code: str) -> StockQuote:
        return StockQuote(code=code, name="测试股票", price=10.5, change_pct=1.2)

    def get_daily_bars(self, code: str, start: date, end: date):
        return []


def test_market_data_service_returns_quote():
    service = MarketDataService(provider=FakeProvider())

    quote = service.get_quote("000001")

    assert quote.code == "000001"
    assert quote.price == 10.5
```

**Step 2: Implement schemas**

```python
# backend/app/schemas/market.py
from datetime import date

from pydantic import BaseModel


class StockQuote(BaseModel):
    code: str
    name: str
    price: float
    change_pct: float | None = None
    volume: float | None = None
    turnover: float | None = None


class DailyBar(BaseModel):
    code: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    turnover: float | None = None
```

**Step 3: Implement provider protocol and service**

```python
# backend/app/services/data/provider.py
from datetime import date
from typing import Protocol

from app.schemas.market import DailyBar, StockQuote


class MarketDataProvider(Protocol):
    def get_quote(self, code: str) -> StockQuote:
        ...

    def get_daily_bars(self, code: str, start: date, end: date) -> list[DailyBar]:
        ...
```

`MarketDataService` delegates to the provider and becomes the stable internal interface.

**Step 4: Implement AKShare provider**

Use AKShare only inside `akshare_provider.py`. Normalize Chinese column names into internal schema fields. If a live API call fails, raise `MarketDataError` with provider name and original message.

**Step 5: Run verification**

Run:

```bash
cd backend
python -m pytest tests/services/test_market_data_service.py -v
```

Expected: test passes without network.

**Step 6: Commit**

```bash
git add backend/app/schemas/market.py backend/app/services/data backend/tests/services/test_market_data_service.py
git commit -m "feat: add market data provider interface"
```

## Task 5: Strategy Engine

**Files:**
- Create: `backend/app/schemas/strategy.py`
- Create: `backend/app/services/strategy/indicators.py`
- Create: `backend/app/services/strategy/engine.py`
- Create: `backend/app/services/strategy/builtin.py`
- Test: `backend/tests/services/test_strategy_engine.py`

**Step 1: Write strategy test**

```python
# backend/tests/services/test_strategy_engine.py
from datetime import date, timedelta

from app.schemas.market import DailyBar
from app.services.strategy.builtin import MovingAverageBreakoutStrategy


def test_moving_average_breakout_selects_candidate():
    bars = [
        DailyBar(code="000001", trade_date=date(2026, 4, 1) + timedelta(days=i),
                 open=10 + i * 0.1, high=10.5 + i * 0.1, low=9.8 + i * 0.1,
                 close=10 + i * 0.1, volume=1000 + i * 10)
        for i in range(20)
    ]
    bars[-1] = bars[-1].model_copy(update={"close": 14.0, "volume": 3000})

    result = MovingAverageBreakoutStrategy().evaluate("000001", bars)

    assert result.matched is True
    assert "突破" in result.reason
```

**Step 2: Implement strategy result schema**

```python
# backend/app/schemas/strategy.py
from pydantic import BaseModel, Field


class StrategySignal(BaseModel):
    stock_code: str
    strategy_name: str
    matched: bool
    reason: str
    score: float = 0
    metrics: dict = Field(default_factory=dict)
```

**Step 3: Implement indicators**

Implement simple moving average and volume average helpers. Keep them pure and easy to test.

**Step 4: Implement built-in strategy**

Use a simple first strategy:

- latest close above 5-day moving average
- latest volume above 1.5 times 5-day average volume
- return score based on price and volume strength

**Step 5: Run verification**

Run:

```bash
cd backend
python -m pytest tests/services/test_strategy_engine.py -v
```

Expected: test passes.

**Step 6: Commit**

```bash
git add backend/app/schemas/strategy.py backend/app/services/strategy backend/tests/services/test_strategy_engine.py
git commit -m "feat: add first strategy engine"
```

## Task 6: Snapshot and Paper Trading Services

**Files:**
- Create: `backend/app/schemas/snapshot.py`
- Create: `backend/app/schemas/paper_trading.py`
- Create: `backend/app/services/snapshot/service.py`
- Create: `backend/app/services/paper_trading/service.py`
- Test: `backend/tests/services/test_paper_trading.py`

**Step 1: Write paper-trading test**

```python
# backend/tests/services/test_paper_trading.py
from datetime import date

from app.schemas.paper_trading import PaperOrderCreate
from app.services.paper_trading.service import calculate_order_return


def test_calculate_order_return_for_long_trade():
    order = PaperOrderCreate(
        stock_code="000001",
        stock_name="平安银行",
        trade_date=date(2026, 4, 27),
        entry_price=10,
        quantity=100,
    )

    result = calculate_order_return(order, close_price=11)

    assert result.pnl == 100
    assert result.return_pct == 10
```

**Step 2: Implement schemas**

Use Pydantic schemas for snapshot creation, order creation, and settlement result.

**Step 3: Implement pure settlement function**

```python
def calculate_order_return(order: PaperOrderCreate, close_price: float) -> SettlementResult:
    pnl = (close_price - order.entry_price) * order.quantity
    return_pct = ((close_price - order.entry_price) / order.entry_price) * 100
    return SettlementResult(pnl=round(pnl, 2), return_pct=round(return_pct, 4))
```

**Step 4: Implement DB-backed services**

`SnapshotService` saves candidate data plus quote and metrics. `PaperTradingService` creates one long order for each candidate and later settles by close price.

**Step 5: Run verification**

Run:

```bash
cd backend
python -m pytest tests/services/test_paper_trading.py -v
```

Expected: test passes.

**Step 6: Commit**

```bash
git add backend/app/schemas/snapshot.py backend/app/schemas/paper_trading.py backend/app/services/snapshot backend/app/services/paper_trading backend/tests/services/test_paper_trading.py
git commit -m "feat: add snapshots and paper trading"
```

## Task 7: LLM Reports

**Files:**
- Create: `backend/app/schemas/report.py`
- Create: `backend/app/services/llm/provider.py`
- Create: `backend/app/services/llm/report_service.py`
- Test: `backend/tests/services/test_report_service.py`

**Step 1: Write fallback report test**

```python
# backend/tests/services/test_report_service.py
from app.services.llm.report_service import build_fallback_daily_report


def test_fallback_daily_report_mentions_orders_and_risk():
    report = build_fallback_daily_report(
        trade_date="2026-04-27",
        candidates_count=3,
        orders_count=3,
        total_return_pct=1.25,
    )

    assert "2026-04-27" in report
    assert "3" in report
    assert "风险" in report
```

**Step 2: Implement report schemas**

Report period types: `daily`, `weekly`, `monthly`.

**Step 3: Implement provider interface**

`LlmProvider.generate(prompt: str) -> str`. Add `OpenAICodexProvider` as the default configured provider if API key and model are present; otherwise use fallback generator. Keep the class behind the provider interface so the rest of the app only depends on `LlmProvider`.

**Step 4: Implement report service**

Build structured prompt from snapshots, orders, returns, and market summary. Save both report text and input summary.

**Step 5: Run verification**

Run:

```bash
cd backend
python -m pytest tests/services/test_report_service.py -v
```

Expected: test passes.

**Step 6: Commit**

```bash
git add backend/app/schemas/report.py backend/app/services/llm backend/tests/services/test_report_service.py
git commit -m "feat: add llm report service"
```

## Task 8: Single-Agent Ask Stock

**Files:**
- Create: `backend/app/schemas/ask_stock.py`
- Create: `backend/app/services/ask_stock/tools.py`
- Create: `backend/app/services/ask_stock/agent.py`
- Test: `backend/tests/services/test_ask_stock_agent.py`

**Step 1: Write single-agent test**

```python
# backend/tests/services/test_ask_stock_agent.py
from app.services.ask_stock.agent import AskStockAgent


class FakeTools:
    def get_quote_context(self, query: str) -> str:
        return "000001 当前价 10.50，涨跌幅 1.2%"


def test_ask_stock_agent_uses_tools_in_answer():
    agent = AskStockAgent(tools=FakeTools(), llm_provider=None)

    answer = agent.answer("分析一下 000001")

    assert "000001" in answer
    assert "当前价" in answer
```

**Step 2: Implement tool facade**

Tools should expose quote, bars, indicators, local snapshots, paper orders, and report lookup. First version can return partial context when some data is unavailable.

**Step 3: Implement agent**

Single flow:

1. Parse user query.
2. Gather context from tools.
3. Build prompt.
4. Call LLM provider if configured.
5. Return fallback answer if LLM is unavailable.

**Step 4: Run verification**

Run:

```bash
cd backend
python -m pytest tests/services/test_ask_stock_agent.py -v
```

Expected: test passes.

**Step 5: Commit**

```bash
git add backend/app/schemas/ask_stock.py backend/app/services/ask_stock backend/tests/services/test_ask_stock_agent.py
git commit -m "feat: add single-agent stock qna"
```

## Task 9: API Endpoints and Celery Tasks

**Files:**
- Create: `backend/app/api/routes/strategies.py`
- Create: `backend/app/api/routes/paper_trading.py`
- Create: `backend/app/api/routes/reports.py`
- Create: `backend/app/api/routes/ask_stock.py`
- Create: `backend/app/worker/tasks.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/api/test_strategy_api.py`
- Test: `backend/tests/api/test_ask_stock_api.py`

**Step 1: Write API smoke tests**

```python
# backend/tests/api/test_ask_stock_api.py
from fastapi.testclient import TestClient

from app.main import app


def test_create_ask_session():
    client = TestClient(app)
    response = client.post("/api/ask-stock/sessions", json={"title": "测试会话"})

    assert response.status_code in {200, 201}
    assert "id" in response.json()
```

**Step 2: Implement routers**

Expose:

- `POST /api/strategies/run`
- `GET /api/strategies/runs`
- `GET /api/strategies/runs/{run_id}`
- `POST /api/paper-trading/settle`
- `GET /api/paper-trading/orders`
- `GET /api/paper-trading/returns`
- `POST /api/reports/generate`
- `GET /api/reports`
- `POST /api/ask-stock/sessions`
- `POST /api/ask-stock/sessions/{session_id}/messages`

**Step 3: Implement task wrappers**

Celery tasks call services:

- `run_strategy_task`
- `settle_paper_trading_task`
- `generate_report_task`

**Step 4: Run verification**

Run:

```bash
cd backend
python -m pytest tests/api -v
```

Expected: API smoke tests pass.

**Step 5: Commit**

```bash
git add backend/app/api backend/app/worker/tasks.py backend/tests/api
git commit -m "feat: expose strategy assistant api"
```

## Task 10: Frontend Application

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/pages/AskStockPage.tsx`
- Create: `frontend/src/pages/StrategySimulationPage.tsx`
- Create: `frontend/src/pages/LlmReportsPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/App.test.tsx`

**Step 1: Write frontend render test**

```tsx
// frontend/src/App.test.tsx
import { render, screen } from "@testing-library/react";
import { App } from "./App";

test("renders main navigation", () => {
  render(<App />);

  expect(screen.getByText("问股")).toBeInTheDocument();
  expect(screen.getByText("策略模拟")).toBeInTheDocument();
  expect(screen.getByText("LLM 分析")).toBeInTheDocument();
});
```

**Step 2: Implement API client**

Use `fetch` with a shared base URL from `import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"`.

**Step 3: Implement pages**

- AskStockPage: session list placeholder, message list, input box, send button.
- StrategySimulationPage: strategy selector, run button, candidate table, orders table.
- LlmReportsPage: period tabs, generate button, report list, report detail.

**Step 4: Style as a compact tool UI**

Use a left sidebar, dense tables, restrained colors, and clear empty states.

**Step 5: Run verification**

Run:

```bash
cd frontend
npm test -- --run
```

Expected: frontend tests pass.

**Step 6: Commit**

```bash
git add frontend
git commit -m "feat: add strategy assistant frontend"
```

## Task 11: Docker Compose and Local Run

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `README.md`

**Step 1: Implement compose services**

Services:

- `postgres`
- `redis`
- `backend`
- `worker`
- `frontend`

Expose:

- backend: `http://localhost:8000`
- frontend: `http://localhost:5173`
- postgres: `localhost:5432`
- redis: `localhost:6379`

**Step 2: Document setup**

README sections:

- project purpose
- architecture
- local setup
- environment variables
- common commands
- first workflow to try

**Step 3: Run verification**

Run:

```bash
docker compose config
```

Expected: compose file is valid.

Then run:

```bash
docker compose up --build
```

Expected:

- backend `/health` returns `{"status":"ok"}`
- frontend opens and shows the three app sections
- worker starts without import errors

**Step 4: Commit**

```bash
git add backend/Dockerfile frontend/Dockerfile docker-compose.yml .env.example README.md
git commit -m "chore: add local docker runtime"
```

## Task 12: End-to-End Closed Loop Demo

**Files:**
- Create: `backend/app/services/demo/seed.py`
- Create: `backend/tests/test_closed_loop.py`
- Modify: `README.md`

**Step 1: Write closed-loop test**

```python
# backend/tests/test_closed_loop.py
def test_closed_loop_demo_generates_report():
    # Use fake provider data and in-memory service calls.
    # Run strategy -> create snapshot -> create paper order -> settle -> generate fallback report.
    assert True
```

Replace the placeholder with a real service-level test using fake market data.

**Step 2: Implement demo seed**

Create deterministic sample stocks and bars so the app can demonstrate the loop without live data.

**Step 3: Add README demo instructions**

Document:

1. Start services.
2. Run demo seed.
3. Trigger strategy.
4. Settle paper trading.
5. Generate daily report.
6. Ask a stock question.

**Step 4: Run full verification**

Run:

```bash
cd backend
python -m pytest -v
```

Run:

```bash
cd frontend
npm test -- --run
```

Run:

```bash
docker compose config
```

Expected: all pass.

**Step 5: Commit**

```bash
git add backend/app/services/demo backend/tests/test_closed_loop.py README.md
git commit -m "test: add closed loop demo coverage"
```

## Final Verification Before Delivery

Run:

```bash
git status --short
```

Expected: clean working tree.

Run:

```bash
git log --oneline --decorate -5
```

Expected: recent commits show the scaffold, core features, frontend, runtime, and demo coverage.

Open the frontend and manually verify:

- 问股 page sends a message and receives an answer.
- 策略模拟 page can trigger a strategy run and show candidates/orders.
- LLM 分析 page can generate and display a daily report.

## Execution Recommendation

Use the current repository worktree for implementation because this project starts from an empty repository. If the tree becomes dirty with user edits, switch to an isolated worktree before continuing.
