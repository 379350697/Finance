from sqlalchemy.orm import Session

from app.models.snapshot import StockSnapshot
from app.schemas.snapshot import StockSnapshotCreate


class SnapshotService:
    def __init__(self, db: Session):
        self.db = db

    def create_snapshot(self, data: StockSnapshotCreate) -> StockSnapshot:
        snapshot = StockSnapshot(**data.model_dump())
        self.db.add(snapshot)
        self.db.flush()
        return snapshot
