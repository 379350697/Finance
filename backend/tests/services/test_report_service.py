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
