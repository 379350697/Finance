from app.services.demo.seed import run_closed_loop_demo


def test_closed_loop_demo_generates_report():
    result = run_closed_loop_demo()

    assert result["signal"].matched is True
    assert result["snapshot"].stock_code == "000001"
    assert result["settlement"].pnl == 100
    assert "2026-04-27" in result["report"]
    assert "风险" in result["report"]
