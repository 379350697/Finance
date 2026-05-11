from fastapi import APIRouter

from app.api.routes import ask_stock, backtests, data_sync, factors, llm_oauth, market, models, paper_trading, reports, strategies

router = APIRouter()
router.include_router(strategies.router)
router.include_router(backtests.router)
router.include_router(paper_trading.router)
router.include_router(reports.router)
router.include_router(ask_stock.router)
router.include_router(llm_oauth.router)
router.include_router(data_sync.router)
router.include_router(factors.router)
router.include_router(market.router)
router.include_router(models.router)
