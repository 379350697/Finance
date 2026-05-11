"""Factor computation and analysis API routes."""

from datetime import date

from fastapi import APIRouter

from app.schemas.factor import FactorComputeRequest, FactorComputeResponse
from app.services.factor.engine import FactorEngine
from app.services.factor.alpha158 import Alpha158
from app.services.factor.alpha360 import Alpha360

router = APIRouter(prefix="/factors", tags=["factors"])

_ALPHA_CLASSES = {"alpha158": Alpha158, "alpha360": Alpha360}


def _get_factor_names(factor_set: str) -> list[str]:
    cls = _ALPHA_CLASSES.get(factor_set)
    if cls is None:
        return []
    exprs = cls.build_expressions()
    return [e.name for e in exprs]


@router.post("/compute", response_model=FactorComputeResponse)
def compute_factors(req: FactorComputeRequest) -> FactorComputeResponse:
    codes = req.codes
    engine = FactorEngine()
    result = engine.compute_factors(codes, req.start_date, req.end_date, req.factor_set)
    names = _get_factor_names(req.factor_set)
    return FactorComputeResponse(
        codes_count=len(result),
        factor_count=len(names),
        date_range=(req.start_date, req.end_date),
        factor_names=names,
        status="completed",
    )


@router.get("/names/{factor_set}")
def list_factor_names(factor_set: str) -> list[str]:
    return _get_factor_names(factor_set)
