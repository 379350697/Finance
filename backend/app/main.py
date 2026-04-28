from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.core.config import settings
from app.services.data.cache import ParquetCache
from app.db.session import engine
from app.db.base import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create tables for SQLite if they don't exist
    Base.metadata.create_all(bind=engine)
    
    # Initialize scheduler
    scheduler = BackgroundScheduler()
    cache = ParquetCache()
    # Schedule sync_all every day at 18:00
    scheduler.add_job(cache.sync_all, 'cron', hour=18, minute=0)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

