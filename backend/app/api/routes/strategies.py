from datetime import date
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, status
from pydantic import BaseModel, Field

from app.services.strategy.registry import default_strategy_registry
from app.services.strategy.executor import execute_strategy_run

router = APIRouter(prefix="/strategies", tags=["strategies"])

_strategy_runs: dict[str, dict] = {}


class StrategyRunRequest(BaseModel):
    strategy_name: str = "moving_average_breakout"
    trade_date: date
    parameters: dict = Field(default_factory=dict)


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
def run_strategy(request: StrategyRunRequest, background_tasks: BackgroundTasks) -> dict:
    registry = default_strategy_registry()
    strategy = registry.get(request.strategy_name)
    task_id = str(uuid4())
    _strategy_runs[task_id] = {
        "id": task_id,
        "task_id": task_id,
        "strategy_name": strategy.name,
        "display_name": strategy.display_name,
        "trade_date": request.trade_date.isoformat(),
        "parameters": request.parameters,
        "status": "running",
    }
    
    background_tasks.add_task(
        execute_strategy_run,
        task_id=task_id,
        strategy_name=strategy.name,
        trade_date=request.trade_date,
        parameters=request.parameters
    )
    
    return _strategy_runs[task_id]


@router.get("/runs")
def list_strategy_runs() -> list[dict]:
    return list(_strategy_runs.values())


@router.get("/runs/{run_id}")
def get_strategy_run(run_id: str) -> dict:
    return _strategy_runs.get(run_id, {"id": run_id, "status": "not_found"})
