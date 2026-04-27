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
