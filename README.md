# A Share Strategy Assistant

A lightweight A-share strategy assistant with a heavier-ready backend frame. The first version closes the loop from data retrieval to strategy screening, snapshots, paper trading, LLM reports, and single-agent stock Q&A.

## Modules

- `data`: market data providers and normalized quote/bar interfaces.
- `strategy`: strategy registry, indicators, and screening engines.
- `snapshot`: daily candidate stock snapshots.
- `paper_trading`: local paper orders, positions, and settlement.
- `llm`: OpenAI Codex provider adapter and fallback report generation.
- `ask_stock`: single-agent stock Q&A.
- `worker`: Celery tasks for longer-running jobs.
- `frontend`: compact React tool UI.

## Local Commands

Backend health test:

```bash
cd backend
python -m pytest tests/test_health.py -v
```

Frontend dev server:

```bash
cd frontend
npm install
npm run dev
```

Docker runtime will be added as the implementation fills in the services.
