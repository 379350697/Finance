from app.worker.celery_app import celery_app


@celery_app.task(name="run_strategy_task")
def run_strategy_task(strategy_name: str, trade_date: str, parameters: dict | None = None) -> dict:
    return {
        "strategy_name": strategy_name,
        "trade_date": trade_date,
        "parameters": parameters or {},
        "status": "completed",
    }


@celery_app.task(name="settle_paper_trading_task")
def settle_paper_trading_task(trade_date: str) -> dict:
    return {"trade_date": trade_date, "status": "completed"}


@celery_app.task(name="generate_report_task")
def generate_report_task(period_type: str, period_start: str, period_end: str) -> dict:
    return {
        "period_type": period_type,
        "period_start": period_start,
        "period_end": period_end,
        "status": "completed",
    }
