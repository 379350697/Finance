from fastapi import APIRouter

from app.api.routes import ask_stock, backtests, paper_trading, reports, strategies

router = APIRouter()
router.include_router(strategies.router)
router.include_router(backtests.router)
router.include_router(paper_trading.router)
router.include_router(reports.router)
router.include_router(ask_stock.router)
