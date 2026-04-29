from datetime import date
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, status, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.models.strategy import StrategyRun
from app.services.strategy.registry import default_strategy_registry
from app.services.strategy.executor import execute_strategy_run

router = APIRouter(prefix="/strategies", tags=["strategies"])


class StrategyRunRequest(BaseModel):
    strategy_name: str = "moving_average_breakout"
    trade_date: date
    parameters: dict = Field(default_factory=dict)


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
def run_strategy(
    request: StrategyRunRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> dict:
    running = db.scalars(
        select(StrategyRun).where(
            StrategyRun.status.in_(["running", "paused"]),
            StrategyRun.strategy_name == request.strategy_name
        )
    ).first()
    if running:
        registry = default_strategy_registry()
        strategy = registry.get(request.strategy_name)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{strategy.display_name}策略已在运行中，请先终止或暂停现有任务，或切换其他策略。"
        )

    registry = default_strategy_registry()
    strategy = registry.get(request.strategy_name)
    
    params = request.parameters.copy()
    params["display_name"] = strategy.display_name
    
    run_record = StrategyRun(
        strategy_name=strategy.name,
        trade_date=request.trade_date,
        status="running",
        parameters=params,
    )
    db.add(run_record)
    db.commit()
    db.refresh(run_record)
    
    import threading
    
    task_id = run_record.id
    
    # Run in a completely separate daemon thread so it never exhausts FastAPI's anyio worker pool
    thread = threading.Thread(
        target=execute_strategy_run,
        kwargs={
            "task_id": task_id,
            "strategy_name": strategy.name,
            "trade_date": request.trade_date,
            "parameters": request.parameters
        },
        daemon=True
    )
    thread.start()
    
    return {
        "id": run_record.id,
        "task_id": run_record.id,
        "strategy_name": run_record.strategy_name,
        "display_name": run_record.parameters.get("display_name", run_record.strategy_name),
        "trade_date": run_record.trade_date.isoformat(),
        "parameters": run_record.parameters,
        "status": run_record.status,
    }


@router.get("/runs")
def list_strategy_runs(db: Session = Depends(get_db)) -> list[dict]:
    runs = db.scalars(
        select(StrategyRun)
        .order_by(StrategyRun.created_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": r.id,
            "task_id": r.id,
            "strategy_name": r.strategy_name,
            "display_name": r.parameters.get("display_name", r.strategy_name),
            "trade_date": r.trade_date.isoformat(),
            "parameters": r.parameters,
            "status": r.status,
            "matched_count": r.parameters.get("last_matched_count", 0),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "error_message": r.error_message,
        }
        for r in runs
    ]


@router.get("/runs/{run_id}")
def get_strategy_run(run_id: str, db: Session = Depends(get_db)) -> dict:
    r = db.get(StrategyRun, run_id)
    if not r:
        return {"id": run_id, "status": "not_found"}
    return {
        "id": r.id,
        "task_id": r.id,
        "strategy_name": r.strategy_name,
        "display_name": r.parameters.get("display_name", r.strategy_name),
        "trade_date": r.trade_date.isoformat(),
        "parameters": r.parameters,
        "status": r.status,
        "matched_count": r.parameters.get("last_matched_count", 0),
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "error_message": r.error_message,
    }


@router.post("/runs/{run_id}/pause")
def pause_strategy_run(run_id: str, db: Session = Depends(get_db)) -> dict:
    r = db.get(StrategyRun, run_id)
    if not r:
        raise HTTPException(status_code=404, detail="Run not found")
    if r.status == "running":
        r.status = "paused"
        db.commit()
    return {"id": r.id, "status": r.status}


@router.post("/runs/{run_id}/resume")
def resume_strategy_run(run_id: str, db: Session = Depends(get_db)) -> dict:
    r = db.get(StrategyRun, run_id)
    if not r:
        raise HTTPException(status_code=404, detail="Run not found")
    if r.status == "paused":
        r.status = "running"
        db.commit()
    return {"id": r.id, "status": r.status}


@router.post("/runs/{run_id}/terminate")
def terminate_strategy_run(run_id: str, db: Session = Depends(get_db)) -> dict:
    from datetime import datetime, UTC
    r = db.get(StrategyRun, run_id)
    if not r:
        raise HTTPException(status_code=404, detail="Run not found")
    if r.status in ["running", "paused"]:
        r.status = "terminated"
        r.completed_at = datetime.now(UTC)
        db.commit()
    return {"id": r.id, "status": r.status}
