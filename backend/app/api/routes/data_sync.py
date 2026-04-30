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

@router.get("/status")
def get_sync_status() -> dict[str, int]:
    import os
    import glob
    from pathlib import Path
    
    data_dir = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) / "data" / "daily"
    if not data_dir.exists():
        return {"cached_count": 0}
        
    files = glob.glob(str(data_dir / "*.parquet"))
    return {"cached_count": len(files)}
