import asyncio

from fastapi import APIRouter, BackgroundTasks

from app.services.data.cache import ParquetCache

router = APIRouter(prefix="/data", tags=["data"])


def sync_market_data_background():
    cache = ParquetCache()
    cache.sync_all()


@router.post("/sync")
def sync_market_data(background_tasks: BackgroundTasks) -> dict[str, str]:
    background_tasks.add_task(sync_market_data_background)
    return {"status": "同步任务已提交后台运行"}
