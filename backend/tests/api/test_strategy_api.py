from fastapi.testclient import TestClient

from app.main import app


def test_run_strategy_returns_task_id():
    client = TestClient(app)
    response = client.post(
        "/api/strategies/run",
        json={"strategy_name": "moving_average_breakout", "trade_date": "2026-04-27"},
    )

    assert response.status_code == 202
    assert "task_id" in response.json()


def test_run_trend_reversal_strategy_returns_display_name():
    client = TestClient(app)
    response = client.post(
        "/api/strategies/run",
        json={"strategy_name": "trend_reversal", "trade_date": "2026-04-27"},
    )

    assert response.status_code == 202
    assert response.json()["display_name"] == "趋势反转策略"
