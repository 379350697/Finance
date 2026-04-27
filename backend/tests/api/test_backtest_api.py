from fastapi.testclient import TestClient

from app.main import app
from tests.services.test_backtest_service import make_breakout_bars


def test_run_backtest_api_returns_summary_and_trades():
    client = TestClient(app)
    response = client.post(
        "/api/backtests/run",
        json={
            "strategy_name": "moving_average_breakout",
            "start_date": "2026-01-01",
            "end_date": "2026-01-08",
            "stock_pool": ["000001"],
            "stocks": [
                {
                    "code": "000001",
                    "name": "Ping An Bank",
                    "bars": [bar.model_dump(mode="json") for bar in make_breakout_bars("000001")],
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_name"] == "moving_average_breakout"
    assert payload["trade_count"] == 1
    assert payload["win_rate"] == 1.0
    assert payload["total_return_pct"] == 0.77
    assert payload["trades"][0]["stock_code"] == "000001"
