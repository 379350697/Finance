from app.db.base import Base, import_models


def test_expected_tables_are_registered():
    import_models()
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
