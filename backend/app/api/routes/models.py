"""Model training and prediction API routes."""

from fastapi import APIRouter, HTTPException, status

from app.schemas.factor import (
    ModelPredictRequest,
    ModelPredictResponse,
    ModelTrainRequest,
    ModelTrainResponse,
    StockScore,
)
from app.services.model.trainer import ModelConfig, ModelTrainer
from app.services.model.predictor import ModelPredictor

router = APIRouter(prefix="/models", tags=["models"])


@router.post("/train", response_model=ModelTrainResponse)
def train_model(req: ModelTrainRequest) -> ModelTrainResponse:
    config = ModelConfig(
        model_name=req.model_name,
        model_type=req.model_type,
        factor_set=req.factor_set,
        train_start=req.train_start,
        train_end=req.train_end,
        valid_start=req.valid_start,
        valid_end=req.valid_end,
        test_start=req.test_start,
        test_end=req.test_end,
        stock_pool=req.stock_pool,
        label_type=req.label_type,
        **req.hyperparams,
    )
    trainer = ModelTrainer()
    result = trainer.train(config)
    return ModelTrainResponse(
        model_name=result.model_name,
        model_type=result.model_type,
        factor_set=result.factor_set,
        ic_mean=result.ic_mean,
        ic_std=result.ic_std,
        icir=result.icir,
        rank_ic_mean=result.rank_ic_mean,
        rank_ic_std=result.rank_ic_std,
        rank_icir=result.rank_icir,
        mse=result.mse,
        mae=result.mae,
        feature_importance=result.feature_importance,
        status="completed",
    )


@router.post("/predict", response_model=ModelPredictResponse)
def predict(req: ModelPredictRequest) -> ModelPredictResponse:
    predictor = ModelPredictor()
    df = predictor.predict(
        model_name=req.model_name,
        codes=req.codes,
        predict_date=req.predict_date,
    )
    predictions = [
        StockScore(code=row["code"], score=row["score"], rank=row["rank"])
        for _, row in df.iterrows()
    ]
    return ModelPredictResponse(predictions=predictions)


@router.get("")
def list_models() -> list[dict]:
    trainer = ModelTrainer()
    names = trainer.list_trained_models()
    return [{"model_name": n} for n in names]


@router.get("/{model_name}")
def get_model(model_name: str) -> dict:
    trainer = ModelTrainer()
    names = trainer.list_trained_models()
    if model_name not in names:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    return {"model_name": model_name, "status": "trained"}
